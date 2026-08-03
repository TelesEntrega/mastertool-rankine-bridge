# -*- coding: utf-8 -*-
r"""40_build_w1_4.py -- marco W1.4: `build` do arquivo SALVO, em abertura
SEPARADA, sobre a saida de `probes/38`.

Contrato: `docs/28`. Plano normativo: `docs/32` secoes 3, 4 e 5.

UMA unica invocacao mutavel, e so uma, com a guarda na linha IMEDIATAMENTE
anterior:

    assert_controlled_write_allowed("build")
    application.build()

Por que abertura separada: compilar na sessao que acabou de escrever provaria,
no maximo, que o texto EM MEMORIA compila. A reabertura remove a ambiguidade --
o que compila e o texto PERSISTIDO (`docs/32` secao 3).

Por que `build` conta como operacao mutavel mesmo "so compilando": ela e a
primeira operacao de W1 que pode acionar comportamento fora do controle direto
do script (resolucao de biblioteca), e por isso passa pela mesma porta unica de
autorizacao. `download_missing_libraries` e `set_compilerversion_to_newest`
seguem PROIBIDAS sem excecao, e nao aparecem neste arquivo.

AVISO NAO E ERRO. O criterio de sucesso e "sem erro" -- `Severity` de erro
ausente na coleta --, com TODOS os avisos registrados na integra no artefato.
Descartar ou resumir avisos apagaria a unica evidencia de que a sessao os viu e
decidiu que nao bloqueavam (`docs/32` secao 5).

Severidade que este arquivo nao consegue classificar NAO vira "sem erro": ela
produz `severity_unclassified`, que nao e sucesso. Fail-closed: um enum
desconhecido lido como aviso seria exatamente o modo de falha que faria um
build com erro passar por aprovado.

NAO SALVA. Nao ha `save`, `save_as`, `save_archive`, `rebuild`, `clean` nem
`create_boot_application` neste arquivo, e o SHA-256 do arquivo de saida e
medido ANTES e DEPOIS do build: se o build alterou o arquivo em disco, isso e
achado, e a sessao reprova.

FONTE DAS MENSAGENS -- lacuna FECHADA na run-019. Este arquivo declarava que
nenhum acessor de colecao de mensagens estava catalogado, e parava em
`messages_unavailable` em vez de dizer "sem erro" sem ter lido nada. A recusa
estava certa, e foi ela que forcou a busca.

Quem respondeu foi a docstring do PROPRIO `build()`, no stub que o produto
versiona (`ScriptApplication.pyi` L41-49): "You can use the System.get_messages
and System.get_message_objects calls to check whether any messages were added".
A lacuna era do CATALOGO, e nao da API.

ITERAR AS CATEGORIAS E ESSENCIAL. O default de `get_message_objects` e a
categoria `ScriptMessage`, onde o proprio script escreve com `write_message`;
as mensagens de COMPILACAO vivem em outra categoria, e usar o default
devolveria vazio -- vazio que leria como "build sem erro".

Duas conversoes medidas no caminho, ambas da familia do erro que reprovou a
run-005: `get_message_categories` devolve `System.Guid` e `get_message_objects`
exige `str`; e `severities` como inteiro levanta "expected Severity, got long",
por isso o parametro e OMITIDO -- o default do produto ja significa "todas".

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
REPO_ROOT = os.path.abspath(os.path.join(_MASTERTOOL_DIR, "..", "..")) if _MASTERTOOL_DIR else None

SCRIPT_NAME = "40_build_w1_4.py"
SCHEMA_VERSION = "1.0"

EXPECTED_PHASE = "W1_4_INTEGRATED_BUILD"
EXPECTED_OPERATION_ID = "w1-4-integrated-build"

# FASES EM QUE COMPILAR E LEGITIMO -- conjunto LITERAL e FECHADO.
#
# `build` verifica; ele nao autoria. Depois de W1.4, outros marcos precisam da
# MESMA verificacao sobre a saida deles -- W2 e o primeiro --, e duplicar este
# probe por marco produziria copias que divergem em silencio.
#
# O conjunto e fechado de proposito: acrescentar fase aqui e decisao humana no
# mesmo commit que abre a fase, e nao consequencia de um plano declarar um
# nome novo. Um probe que aceitasse "a fase que o plano disser" nao teria
# fase alguma.
ACCEPTED_BUILD_PHASES = ("W1_4_INTEGRATED_BUILD", "W2_VERIFY_BUILD",
                         "W3_VERIFY_BUILD", "W4_VERIFY_BUILD",
                         "W5_VERIFY_BUILD", "W6_VERIFY_BUILD",
                         "W7_VERIFY_BUILD", "W8_VERIFY_BUILD",
                         "W9_VERIFY_BUILD",
                         "W10_VERIFY_BUILD",
                         "W10_REVERT_VERIFY_BUILD")
ACCEPTED_OPERATION_IDS = ("w1-4-integrated-build", "w2-verify-build",
                          "w3-idiomatic-call", "w4-factory-build",
                          "w5-prove-iec-package", "w6-prove-dut-and-task",
                          "w7-factory-full", "w8-prove-task-with-pou",
                          "w9-prove-task-timing",
                          "w10-edit-existing", "w10-revert")
EXPECTED_CONTAINER_NAME = "Application"
EXPECTED_CONTAINER_TYPE_GUID = "639b491f-5557-464c-af91-1471bac9f549"

# O plano descreve a cadeia INTEIRA (a mesma tupla que `probes/38` confere);
# este arquivo executa apenas a ultima operacao dela.
EXPECTED_PLAN_OPERATIONS = ("create_gvl", "create_program", "replace",
                            "replace", "replace", "save_as", "build")

# A cadeia esperada POR FASE.
#
# Antes disto havia uma tupla so, a de W1.4, exigida de todo plano de build. O
# efeito apareceu em W2: para compilar a saida de `add` + `save_as`, o plano de
# build de W2 teve de declarar a cadeia de W1.4 -- ou seja, o plano descrevia
# operacoes que NAO produziram aquele artefato. Passava na validacao e mentia
# no registro.
#
# `W2_VERIFY_BUILD` fica com a cadeia de W1.4 de proposito: e o registro do que
# a run-021 de fato executou, e reescrever aqui invalidaria um plano ja
# executado e documentado em docs/39. Corrigir para frente, sem reescrever
# historia.
EXPECTED_PLAN_OPERATIONS_BY_PHASE = {
    "W1_4_INTEGRATED_BUILD": EXPECTED_PLAN_OPERATIONS,
    "W2_VERIFY_BUILD": EXPECTED_PLAN_OPERATIONS,
    "W3_VERIFY_BUILD": ("replace", "save_as", "build"),
    # A FABRICA: a cadeia varia com a spec, entao a tupla fixa nao serve.
    # O plano de build de W4 declara so o que ESTA etapa faz -- compilar --
    # e a cadeia de autoria fica no plano do planner, que tem hash proprio
    # e e citado no artefato. Declarar aqui a cadeia inteira obrigaria a
    # reescrever este arquivo a cada spec nova, e um arquivo que muda por
    # spec deixa de ser conjunto fechado.
    "W4_VERIFY_BUILD": ("build",),
    "W5_VERIFY_BUILD": ("build",),
    "W6_VERIFY_BUILD": ("build",),
    "W7_VERIFY_BUILD": ("build",),
    "W8_VERIFY_BUILD": ("build",),
    "W9_VERIFY_BUILD": ("build",),
    "W10_VERIFY_BUILD": ("build",),
    "W10_REVERT_VERIFY_BUILD": ("build",),
}
EXECUTED_OPERATION = "build"

CALL_SITE_BUILD = "probes/40_build_w1_4.py::build_guarded"

# Campos de `ScriptMessage`, nas DUAS grafias catalogadas: `docs/27` secao 6
# lista `Text`/`Severity`/`Position`/`ObjectGuid`; a observacao estatica em
# `docs/api/mastertool-api-observations.md` lista `text`/`severity`/
# `position`/`object`. Os dois conjuntos sao catalogados, e por isso os dois
# sao tentados -- nenhum nome fora destes e lido.
MESSAGE_FIELD_ALTERNATIVES = {
    "severity": ("severity", "Severity"),
    "text": ("text", "Text"),
    "position": ("position", "Position"),
    "object": ("object", "ObjectGuid"),
}

SEVERITY_ERROR = "error"
SEVERITY_WARNING = "warning"
SEVERITY_INFORMATION = "information"
SEVERITY_UNCLASSIFIED = "unclassified"

# Classificacao por conteudo textual da representacao do enum. Ordem importa:
# "error" e testado antes de qualquer outro, e nada fora desta tabela vira
# aviso por conveniencia.
SEVERITY_KEYWORDS = (
    ("error", SEVERITY_ERROR),
    ("fatal", SEVERITY_ERROR),
    ("warning", SEVERITY_WARNING),
    ("information", SEVERITY_INFORMATION),
    ("info", SEVERITY_INFORMATION),
    # `Text` e o quinto membro do enum `Severity` (ScriptSystem.pyi L80-84):
    # "informational text without corresponding source code position". Faltava
    # na tabela, e por isso a run-019 leu as oito mensagens do build -- inclusive
    # "Compile complete -- 0 errors, 0 warnings" -- e classificou TODAS como
    # `unclassified`, reprovando por severidade desconhecida.
    #
    # A reprovacao estava CERTA: severidade que a tabela nao conhece nao pode
    # virar aviso por conveniencia, senao um erro desconhecido passaria por
    # aprovado. O defeito era a tabela estar incompleta, e nao a regra.
    #
    # Entra como informacao, e nao como aviso: o proprio enum a descreve como
    # texto informativo. Fica DEPOIS de "error" e "warning" de proposito -- a
    # comparacao e por substring, e uma mensagem de erro que contivesse a
    # palavra "text" nao pode ser rebaixada.
    ("text", SEVERITY_INFORMATION),
)

MESSAGE_SOURCE_GAP = (
    "nenhum acessor de colecao de mensagens de compilacao esta catalogado em "
    "docs/27 nem em docs/api/mastertool-api-observations.md a partir de "
    "IScriptApplication ou do objeto system. Este probe coleta apenas o que a "
    "propria build() devolver; quando ela nao devolve colecao, a sessao NAO e "
    "aprovada. Fechar a lacuna e reconhecimento read-only proprio."
)

# --- estados, vocabulario fechado --------------------------------------------
STATUS_PRECONDITION_FAILED = "precondition_failed"
STATUS_REOPEN_FAILED = "reopen_failed"
STATUS_BUILD_FAILED = "build_failed"
STATUS_MESSAGES_UNAVAILABLE = "messages_unavailable"
# O build nao produziu mensagem alguma. Nao e "compilou limpo": e ausencia de
# evidencia sobre a compilacao. Status PROPRIO, e nao `messages_unavailable`,
# porque as duas causas pedem investigacoes opostas -- la a fonte nao pode ser
# lida; aqui ela foi lida e veio vazia.
STATUS_NO_BUILD_MESSAGES = "no_build_messages"
STATUS_SEVERITY_UNCLASSIFIED = "severity_unclassified"
STATUS_OUTPUT_MODIFIED_BY_BUILD = "output_modified_by_build"
STATUS_BUILD_VERIFIED = "build_verified"
STATUS_FATAL = "fatal"

ALL_STATUSES = (
    STATUS_PRECONDITION_FAILED, STATUS_REOPEN_FAILED, STATUS_BUILD_FAILED,
    STATUS_MESSAGES_UNAVAILABLE, STATUS_NO_BUILD_MESSAGES,
    STATUS_SEVERITY_UNCLASSIFIED,
    STATUS_OUTPUT_MODIFIED_BY_BUILD, STATUS_BUILD_VERIFIED, STATUS_FATAL,
)

SUCCESS_STATUSES = (STATUS_BUILD_VERIFIED,)

EXIT_BY_STATUS = {
    STATUS_BUILD_VERIFIED: 0,
    STATUS_PRECONDITION_FAILED: 2,
    STATUS_REOPEN_FAILED: 2,
    STATUS_BUILD_FAILED: 3,
    STATUS_SEVERITY_UNCLASSIFIED: 3,
    STATUS_OUTPUT_MODIFIED_BY_BUILD: 3,
    STATUS_MESSAGES_UNAVAILABLE: 4,
    STATUS_NO_BUILD_MESSAGES: 4,
    STATUS_FATAL: 1,
}

# O build acontece sobre a SAIDA de `probes/38`, que ja e artefato. Qualquer
# status aqui exige que a saida NAO seja promovida -- mas a copia de trabalho
# de `probes/38` ja foi descartada antes desta etapa, e este arquivo nunca a
# toca.
STATUSES_BLOCKING_PROMOTION = (
    STATUS_PRECONDITION_FAILED, STATUS_REOPEN_FAILED, STATUS_BUILD_FAILED,
    STATUS_MESSAGES_UNAVAILABLE, STATUS_NO_BUILD_MESSAGES,
    STATUS_SEVERITY_UNCLASSIFIED,
    STATUS_OUTPUT_MODIFIED_BY_BUILD, STATUS_FATAL,
)

VOLATILE_FIELDS = ("generated_at", "started_at", "finished_at", "timestamp")

ARTIFACT_NAMES = ("build-manifest.json", "build-journal.jsonl",
                  "build-messages.json", "build-completion.json",
                  "build-report.md")

MAX_MESSAGES_COLLECTED = 5000

try:
    _STRING_TYPES = (basestring,)  # noqa: F821
except NameError:
    _STRING_TYPES = (str,)


def is_text(value):
    return isinstance(value, _STRING_TYPES) and value != ""


def sha256_of_file(path):
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


class Journal(object):
    """Append-only. `mutation_attempt` antes do efeito, `mutation_done`
    depois."""

    def __init__(self, path, now):
        self.path = path
        self.now = now
        self.entries = []

    def record(self, entry):
        ordered = {}
        for key in entry:
            ordered[key] = entry[key]
        ordered["timestamp"] = self.now()
        ordered["sequence"] = len(self.entries)
        self.entries.append(ordered)
        if self.path:
            from common import file_io
            file_io.append_text(self.path, json.dumps(ordered, sort_keys=True) + "\n")
        return ordered


def object_identity(obj):
    identity = {"name": None, "type_guid": None, "is_folder": None, "errors": []}
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
    return identity


# --- classificacao de mensagens (nucleo puro, testavel sem CLR) --------------

def classify_severity(raw_severity):
    """Rotulo fechado a partir da REPRESENTACAO textual do enum.

    Fail-closed: o que nao casa com a tabela literal vira `unclassified`, e
    `unclassified` nao e aviso. Um enum desconhecido tratado como aviso faria
    um build com erro passar por aprovado, que e precisamente o resultado que
    este marco existe para nao produzir.
    """
    if raw_severity is None:
        return SEVERITY_UNCLASSIFIED
    try:
        texto = str(raw_severity).lower()
    except Exception:                                          # noqa: BLE001
        return SEVERITY_UNCLASSIFIED
    for palavra, rotulo in SEVERITY_KEYWORDS:
        if palavra in texto:
            return rotulo
    return SEVERITY_UNCLASSIFIED


def read_message_field(message, field_name):
    """Le UM campo de `ScriptMessage` pelos nomes LITERAIS catalogados.

    Nao ha `getattr` dinamico: os nomes vem da tabela literal
    `MESSAGE_FIELD_ALTERNATIVES` e cada um e testado por `hasattr` com o nome
    escrito no proprio codigo, exatamente como os probes anteriores leem
    `type`, `is_folder` e `has_textual_declaration`.
    """
    alternativas = MESSAGE_FIELD_ALTERNATIVES.get(field_name) or ()
    for nome in alternativas:
        try:
            if not hasattr(message, nome):
                continue
        except Exception:                                      # noqa: BLE001
            continue
        try:
            if nome == "severity":
                return message.severity, nome
            if nome == "Severity":
                return message.Severity, nome
            if nome == "text":
                return message.text, nome
            if nome == "Text":
                return message.Text, nome
            if nome == "position":
                return message.position, nome
            if nome == "Position":
                return message.Position, nome
            if nome == "object":
                return message.object, nome
            if nome == "ObjectGuid":
                return message.ObjectGuid, nome
        except Exception:                                      # noqa: BLE001
            continue
    return None, None


def describe_message(message):
    """Um registro serializavel por mensagem, com os quatro campos pedidos por
    `docs/32` secao 5 e a classificacao de severidade."""
    severidade_bruta, campo_severidade = read_message_field(message, "severity")
    texto, campo_texto = read_message_field(message, "text")
    posicao, campo_posicao = read_message_field(message, "position")
    objeto, campo_objeto = read_message_field(message, "object")

    def _texto_ou_none(valor):
        if valor is None:
            return None
        try:
            return str(valor)
        except Exception:                                      # noqa: BLE001
            return None

    return {
        "severity_raw": _texto_ou_none(severidade_bruta),
        "severity": classify_severity(severidade_bruta),
        "text": _texto_ou_none(texto),
        "position": _texto_ou_none(posicao),
        "object": _texto_ou_none(objeto),
        "fields_read": {"severity": campo_severidade, "text": campo_texto,
                        "position": campo_posicao, "object": campo_objeto},
    }


# O enum `Severity` (ScriptSystem.pyi L64-84) tem cinco membros, com valores
# de FLAG: FatalError=1, Error=2, Warning=4, Information=8, Text=16.
#
# Eles NAO viram constantes deste modulo de proposito. Cheguei a declara-las e
# a guarda de constante morta as reprovou na mesma hora, com razao: depois que
# o parametro `severities` passou a ser OMITIDO -- porque o default do produto
# ja significa "todas" --, elas nao tinham mais leitor. Constante que aparenta
# controlar a filtragem sem controlar nada le como cobertura, e foi assim que
# um GUID de linguagem morto sobreviveu num probe anterior.
#
# O conhecimento fica aqui, em prosa, que e onde ele de fato esta em uso: ele
# explica por que a classificacao textual abaixo tem cinco rotulos.


def collect_messages_from_system(system):
    """Le as mensagens pelo `system`, que e onde o proprio stub de `build()`
    manda procurar.

    Fonte: `ScriptApplication.pyi` L41-49 -- a docstring de `build()` diz
    textualmente "You can use the System.get_messages and
    System.get_message_objects calls to check whether any messages were
    added". E `ScriptSystem.pyi` L375-390 documenta
    `get_message_objects(category=None, severities=0xFFFFFFFF)`, L393
    `get_message_categories(bActive=True)` e L64-84 o enum `Severity`.

    POR QUE ITERAR AS CATEGORIAS, e nao usar o default: o default de
    `get_message_objects` e a categoria `ScriptMessage` (L381), que e onde o
    PROPRIO SCRIPT escreve com `write_message`. As mensagens de COMPILACAO
    vivem em outra categoria. Usar o default devolveria vazio e esse vazio
    leria como "build sem erro" -- exatamente o modo de falha que este probe
    existe para impedir.

    Devolve `(mensagens, disponivel, nota)`. Nunca levanta.
    """
    if system is None:
        return [], False, "objeto `system` indisponivel no escopo do script"
    try:
        categorias = system.get_message_categories(True)
    except Exception as exc:                                       # noqa: BLE001
        return [], False, "get_message_categories falhou: %r" % (exc,)
    if categorias is None:
        return [], False, "get_message_categories devolveu None"

    mensagens = []
    categorias_lidas = []
    falhas = []
    for categoria in categorias:
        # `get_message_categories` devolve `System.Guid`, e
        # `get_message_objects` exige `str` -- medido na run-019:
        # `TypeError: expected str, got Guid`. O stub declara o parametro como
        # "Guid or str" (ScriptSystem.pyi L381), mas o binding do IronPython
        # aceita so o texto.
        #
        # E a MESMA classe do defeito que reprovou a run-005, invertida: la o
        # plano trazia texto e a API exigia `Nullable[Guid]`; aqui a API
        # devolve `Guid` e a outra exige texto. A conversao e explicita e
        # acontece ANTES da chamada, nunca dentro dela.
        try:
            categoria_texto = str(categoria)
        except Exception as exc:                                   # noqa: BLE001
            falhas.append("conversao da categoria para texto falhou: %r" % (exc,))
            continue
        # `severities` é OMITIDO de proposito. O stub declara o default como
        # `0xFFFFFFFF` e diz "By default, all severities are returned"
        # (ScriptSystem.pyi L375-386) -- ou seja, o proprio default ja e o que
        # este probe quer. Passar o inteiro reprovou na run-019 com
        # `TypeError: expected Severity, got long`: o binding exige o valor do
        # ENUM, e o enum nao esta catalogado como global injetado. Usar o
        # default e mais correto que construir o enum por adivinhacao -- e nao
        # reduz cobertura, porque "tudo" e exatamente a intencao.
        try:
            itens = system.get_message_objects(categoria_texto)
        except Exception as exc:                                   # noqa: BLE001
            falhas.append("%s: %r" % (categoria_texto, exc))
            continue
        if itens is None:
            continue
        categorias_lidas.append(categoria)
        try:
            for item in itens:
                mensagens.append(describe_message(item))
                if len(mensagens) >= MAX_MESSAGES_COLLECTED:
                    return (mensagens, True,
                            "coleta interrompida em %d mensagens (limite do "
                            "probe)" % MAX_MESSAGES_COLLECTED)
        except Exception as exc:                                   # noqa: BLE001
            falhas.append("iteracao em %r: %r" % (categoria, exc))

    if not categorias_lidas:
        return [], False, ("nenhuma categoria de mensagem pode ser lida: %s"
                           % ("; ".join(falhas) or "sem falha registrada"))
    nota = None
    if falhas:
        nota = "categorias com falha: %s" % ("; ".join(falhas),)
    return mensagens, True, nota


def collect_messages(build_result):
    """(mensagens, disponivel, nota). Nunca levanta.

    `build_result` e o valor devolvido pela propria `build()`. Quando ele nao
    e iteravel, nao ha fonte de mensagem catalogada -- e a ausencia e
    registrada como LACUNA, nunca como "nenhuma mensagem".
    """
    if build_result is None:
        return [], False, MESSAGE_SOURCE_GAP
    if isinstance(build_result, _STRING_TYPES):
        return [], False, MESSAGE_SOURCE_GAP
    mensagens = []
    try:
        for item in build_result:
            mensagens.append(describe_message(item))
            if len(mensagens) >= MAX_MESSAGES_COLLECTED:
                return mensagens, True, ("coleta interrompida em %d mensagens "
                                         "(limite do probe)"
                                         % MAX_MESSAGES_COLLECTED)
    except TypeError:
        return [], False, MESSAGE_SOURCE_GAP
    except Exception as exc:                                   # noqa: BLE001
        return mensagens, False, "iteracao das mensagens falhou: %r" % (exc,)
    return mensagens, True, None


def message_identity(message):
    """Chave de identidade de uma mensagem, para comparar antes x depois.

    Usa os campos LIDOS (`severity_raw`, `text`, `position`, `object`), e nao o
    objeto .NET: o mesmo texto reaparece como outro objeto a cada leitura, e
    comparar identidade de objeto marcaria tudo como novo.
    """
    return (message.get("severity_raw"), message.get("text"),
            message.get("position"), message.get("object"))


def mark_pre_existing(messages, baseline):
    """Marca `pre_existing` nas mensagens que ja estavam la ANTES do build.

    MULTICONJUNTO, e nao conjunto: se o texto aparece duas vezes depois e uma
    vez antes, apenas UMA e pre-existente. Com semantica de conjunto, um erro
    de compilacao com o mesmo texto de uma mensagem anterior sumiria do resumo
    -- e sumir do resumo e sumir do veredito.
    """
    restantes = {}
    for anterior in baseline or []:
        chave = message_identity(anterior)
        restantes[chave] = restantes.get(chave, 0) + 1
    marcadas = []
    for mensagem in messages or []:
        chave = message_identity(mensagem)
        pre = restantes.get(chave, 0) > 0
        if pre:
            restantes[chave] = restantes[chave] - 1
        copia = dict(mensagem)
        copia["pre_existing"] = pre
        marcadas.append(copia)
    return marcadas


def messages_from_build(messages):
    """Somente as que o build produziu."""
    return [m for m in messages or [] if not m.get("pre_existing")]


def summarize_messages(messages):
    resumo = {SEVERITY_ERROR: 0, SEVERITY_WARNING: 0,
              SEVERITY_INFORMATION: 0, SEVERITY_UNCLASSIFIED: 0}
    for mensagem in messages or []:
        rotulo = mensagem.get("severity")
        if rotulo in resumo:
            resumo[rotulo] = resumo[rotulo] + 1
        else:
            resumo[SEVERITY_UNCLASSIFIED] = resumo[SEVERITY_UNCLASSIFIED] + 1
    return resumo


def classify_build_outcome(messages, available):
    """Status a partir das mensagens que o BUILD produziu. AVISO NAO E ERRO: o
    criterio e ausencia de erro, e os avisos ficam registrados na integra.

    ZERO MENSAGEM NAO E APROVACAO. As tres geracoes medidas (run-019, run-022,
    run-023) produziram as MESMAS cinco linhas de compilador -- "Build
    started", "Typify code", "Compile complete -- 0 errors, 0 warnings",
    "Additional code checks", "Additional code checks complete". Este
    compilador sempre fala. Silencio aqui significa que a leitura falhou ou
    que o build nao rodou, e nos dois casos nao ha evidencia sobre a
    compilacao -- que e coisa diferente de evidencia de que ela deu certo.

    O risco e concreto desde que o probe passou a descontar a linha de base:
    um desconto largo demais esvaziaria a lista, e a lista vazia leria como
    "compilou limpo". A regra existe para que esse modo de falha tenha nome.
    """
    if not available:
        return STATUS_MESSAGES_UNAVAILABLE
    if not messages:
        return STATUS_NO_BUILD_MESSAGES
    resumo = summarize_messages(messages)
    if resumo.get(SEVERITY_ERROR):
        return STATUS_BUILD_FAILED
    if resumo.get(SEVERITY_UNCLASSIFIED):
        return STATUS_SEVERITY_UNCLASSIFIED
    return STATUS_BUILD_VERIFIED


# --- a UNICA chamada mutavel -------------------------------------------------

def build_guarded(application, safety):
    """A unica operacao mutavel deste arquivo. Entre a guarda e a chamada nao
    ha ramo, laco, wrapper nem log."""
    safety.assert_controlled_write_allowed("build")
    build_result = application.build()
    return build_result


def run_build(script_globals, argv, safety, project_access, file_io, probe_cli,
              now=None):
    """Executa o `build` de W1.4 sobre o arquivo ja salvo. Injecao explicita
    dos modulos para teste com dubles."""
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
        "opened_project": None,
        "output_project": {"path": None, "sha256_expected": None,
                           "sha256_before_build": None,
                           "sha256_after_build": None, "unchanged": None},
        "container_node_path": None,
        "container_identity": None,
        "operations_requested": [],
        "operations_authorized": [],
        "operations_executed": [],
        "messages": [],
        "message_summary": None,
        "messages_available": None,
        "problems": [],
        "gap_notes": [],
        "runtime": None,
        "artifacts_dir": None,
        "exit_code": EXIT_BY_STATUS[STATUS_FATAL],
    }
    journal = Journal(None, now)

    def finish(status):
        result["status"] = status
        result["finished_at"] = now()
        result["exit_code"] = EXIT_BY_STATUS.get(status, EXIT_BY_STATUS[STATUS_FATAL])
        result["blocks_promotion"] = status in STATUSES_BLOCKING_PROMOTION
        result["journal"] = journal.entries
        return result

    problems = []
    plan_path = probe_cli.find_arg(argv, "plan")
    result["plan_path"] = plan_path
    artifacts_dir = probe_cli.validate_output_path(
        probe_cli.find_arg(argv, "output"), REPO_ROOT, problems)
    result["artifacts_dir"] = artifacts_dir
    expected_output_hash = probe_cli.find_arg(argv, "output-sha256")
    result["output_project"]["sha256_expected"] = expected_output_hash

    if not is_text(plan_path) or not os.path.isfile(plan_path):
        problems.append("--plan obrigatorio e existente: %r" % (plan_path,))
    if not is_text(expected_output_hash):
        problems.append(
            "--output-sha256 obrigatorio: sem o hash registrado apos o save_as "
            "nao se prova que o build rodou sobre o arquivo autorado")
    if problems:
        result["problems"].extend(problems)
        return finish(STATUS_PRECONDITION_FAILED)

    try:
        plan = load_json_file(plan_path)
    except Exception as exc:                                   # noqa: BLE001
        result["problems"].append("plano ilegivel: %r" % (exc,))
        return finish(STATUS_PRECONDITION_FAILED)

    if plan.get("phase") not in ACCEPTED_BUILD_PHASES:
        result["problems"].append(
            "phase do plano e %r, esperado um de %s"
            % (plan.get("phase"), list(ACCEPTED_BUILD_PHASES)))
        return finish(STATUS_PRECONDITION_FAILED)
    if plan.get("operation_id") not in ACCEPTED_OPERATION_IDS:
        result["problems"].append(
            "operation_id do plano e %r, esperado %r"
            % (plan.get("operation_id"), EXPECTED_OPERATION_ID))
        return finish(STATUS_PRECONDITION_FAILED)
    kinds = tuple([item.get("kind") for item in (plan.get("operations") or [])
                   if isinstance(item, dict)])
    esperadas = EXPECTED_PLAN_OPERATIONS_BY_PHASE.get(plan.get("phase"))
    if esperadas is None:
        # Fase aceita para build sem cadeia declarada: recusa, e nao um
        # fallback silencioso para a cadeia de W1.4. Quem admite uma fase nova
        # declara o que ela produz, no mesmo commit.
        result["problems"].append(
            "fase %r nao tem cadeia esperada declarada em "
            "EXPECTED_PLAN_OPERATIONS_BY_PHASE" % (plan.get("phase"),))
        return finish(STATUS_PRECONDITION_FAILED)
    if kinds != esperadas:
        result["problems"].append(
            "operations do plano devem ser exatamente %s para a fase %s; "
            "recebido %s" % (list(esperadas), plan.get("phase"), list(kinds)))
        return finish(STATUS_PRECONDITION_FAILED)

    journal.path = os.path.join(artifacts_dir, "build-journal.jsonl") \
        if artifacts_dir else None
    journal.record({"event": "plan_accepted", "phase_expected": EXPECTED_PHASE})

    result["runtime"] = probe_cli.runtime_identity()
    expected_version = (plan.get("mastertool") or {}).get("version")
    observed_version = (result["runtime"] or {}).get("file_version")
    if observed_version != expected_version:
        result["problems"].append(
            "instalacao inesperada: observada %r, plano espera %r"
            % (observed_version, expected_version))
        return finish(STATUS_PRECONDITION_FAILED)

    try:
        phase_observed = safety.CONTROLLED_WRITE_PHASE
    except Exception:                                          # noqa: BLE001
        phase_observed = None
    result["phase_observed"] = phase_observed
    if phase_observed not in ACCEPTED_BUILD_PHASES:
        result["problems"].append(
            "fase controlada observada e %r, esperada uma de %s"
            % (phase_observed, list(ACCEPTED_BUILD_PHASES)))
        return finish(STATUS_PRECONDITION_FAILED)

    project, access_error = project_access.get_primary_project(script_globals)
    if project is None:
        result["problems"].append(
            "sem projeto primario na reabertura: %s. Saida tratada como "
            "invalida e NAO promovida -- nunca reaberta a forca." % (access_error,))
        return finish(STATUS_REOPEN_FAILED)

    opened_path = project_access.get_project_path(project)
    result["opened_project"] = opened_path
    output_path = (plan.get("output_project") or {}).get("path")
    result["output_project"]["path"] = output_path
    if not is_text(opened_path) or not is_text(output_path) or \
            os.path.normcase(os.path.abspath(opened_path)) != \
            os.path.normcase(os.path.abspath(output_path)):
        result["problems"].append(
            "projeto aberto (%r) nao e o output do plano (%r)"
            % (opened_path, output_path))
        return finish(STATUS_REOPEN_FAILED)

    hash_antes, erro_hash = sha256_of_file(opened_path)
    result["output_project"]["sha256_before_build"] = hash_antes
    if erro_hash:
        result["problems"].append("sha256 do output ilegivel: %s" % erro_hash)
        return finish(STATUS_REOPEN_FAILED)
    if hash_antes != expected_output_hash:
        result["problems"].append(
            "sha256 do output (%r) diverge do registrado apos o save_as (%r)"
            % (hash_antes, expected_output_hash))
        return finish(STATUS_REOPEN_FAILED)

    container_spec = plan.get("container") or {}
    node_path = container_spec.get("node_path")
    result["container_node_path"] = node_path
    node_problems = []
    indexes = probe_cli.parse_node_id(node_path, node_problems,
                                      label="container.node_path")
    if indexes is None:
        result["problems"].extend(node_problems)
        return finish(STATUS_PRECONDITION_FAILED)

    trace = []
    application = probe_cli.descend(project, indexes, trace)
    if application is None:
        result["problems"].append(
            "Application nao alcancado pelo node_path %r (trace=%r)"
            % (node_path, trace))
        return finish(STATUS_PRECONDITION_FAILED)

    identity = object_identity(application)
    result["container_identity"] = identity
    if identity.get("name") != EXPECTED_CONTAINER_NAME:
        result["problems"].append(
            "objeto resolvido e %r, esperado %r"
            % (identity.get("name"), EXPECTED_CONTAINER_NAME))
        return finish(STATUS_PRECONDITION_FAILED)
    if identity.get("type_guid") != EXPECTED_CONTAINER_TYPE_GUID:
        result["problems"].append(
            "type do objeto resolvido e %r, esperado %r"
            % (identity.get("type_guid"), EXPECTED_CONTAINER_TYPE_GUID))
        return finish(STATUS_PRECONDITION_FAILED)

    journal.record({"event": "preconditions_passed",
                    "output_sha256_before": hash_antes})

    # --- linha de base do message store, ANTES do build ----------------------
    #
    # ESTE PROBE ESCREVE NO ARMAZEM QUE DEPOIS LE. `print` num script do
    # MasterTool nao vai para stdout: vai para o message store do produto. O
    # banner deste arquivo, portanto, entra na MESMA colecao de onde saem as
    # mensagens do compilador -- e a run-023 mediu 8 mensagens das quais 3 eram
    # o proprio probe se lendo.
    #
    # A direcao do erro era segura (mensagem a mais so poderia reprovar a toa,
    # nunca aprovar), mas a CONTAGEM era falsa: "8 informacoes" nunca foram 8
    # informacoes do compilador. E a classificacao por substring tornava isso
    # fragil: bastaria o probe imprimir uma linha com a palavra "erro" para o
    # build ser reprovado pelo texto do proprio probe.
    #
    # Mensagem que ja existia ANTES do build nao pode ser atribuida ao build.
    mensagens_antes, base_disponivel, base_nota = collect_messages_from_system(
        script_globals.get("system") if script_globals else None)
    if base_nota:
        result["gap_notes"].append("linha de base do message store: %s"
                                   % (base_nota,))
    result["messages_baseline_available"] = base_disponivel
    result["messages_baseline_count"] = len(mensagens_antes)
    journal.record({"event": "message_baseline",
                    "count": len(mensagens_antes),
                    "available": base_disponivel})

    # --- a unica mutacao: build ----------------------------------------------
    result["operations_requested"].append(EXECUTED_OPERATION)
    journal.record({"event": "mutation_attempt", "operation": EXECUTED_OPERATION,
                    "phase": phase_observed, "call_site": CALL_SITE_BUILD,
                    "state_before": {"output_sha256": hash_antes}})
    try:
        build_result = build_guarded(application, safety)
    except safety.SafetyError as exc:
        result["problems"].append("autorizacao de build recusada: %s" % (exc,))
        journal.record({"event": "mutation_denied", "operation": EXECUTED_OPERATION,
                        "call_site": CALL_SITE_BUILD, "error": repr(exc)})
        return finish(STATUS_PRECONDITION_FAILED)
    except Exception as exc:                                   # noqa: BLE001
        result["problems"].append("build levantou: %r" % (exc,))
        journal.record({"event": "mutation_failed", "operation": EXECUTED_OPERATION,
                        "call_site": CALL_SITE_BUILD, "error": repr(exc)})
        return finish(STATUS_BUILD_FAILED)

    result["operations_authorized"].append(EXECUTED_OPERATION)
    result["operations_executed"].append(EXECUTED_OPERATION)
    journal.record({"event": "mutation_done", "operation": EXECUTED_OPERATION,
                    "call_site": CALL_SITE_BUILD})

    # DUAS FONTES, nesta ordem, e as duas catalogadas. O retorno de `build()`
    # e consultado primeiro por ser o mais direto; o `system` entra porque a
    # docstring do PROPRIO `build()` manda usa-lo (ScriptApplication.pyi
    # L41-49). Medido na run-019: `build()` nao devolve colecao, e sem a
    # segunda fonte o status ficava `messages_unavailable` -- correto, mas
    # incapaz de concluir a cadeia.
    mensagens, disponivel, nota = collect_messages(build_result)
    if not disponivel:
        nota_retorno = nota
        mensagens, disponivel, nota = collect_messages_from_system(
            script_globals.get("system") if script_globals else None)
        if nota_retorno:
            nota = ("retorno de build(): %s | system: %s"
                    % (nota_retorno, nota or "ok"))
    # Desconta o que ja estava no armazem antes do build -- inclusive o banner
    # deste proprio probe. O RESUMO, que decide o status, conta apenas o que o
    # build produziu; o total fica registrado ao lado, para que a diferenca
    # seja auditavel em vez de silenciosa.
    mensagens = mark_pre_existing(mensagens, mensagens_antes)
    do_build = messages_from_build(mensagens)
    result["messages"] = mensagens
    result["messages_available"] = disponivel
    result["message_summary"] = summarize_messages(do_build)
    result["message_summary_including_pre_existing"] = summarize_messages(
        mensagens)
    result["message_count_total"] = len(mensagens)
    result["message_count_from_build"] = len(do_build)
    if nota:
        result["gap_notes"].append(nota)

    hash_depois, erro_depois = sha256_of_file(opened_path)
    result["output_project"]["sha256_after_build"] = hash_depois
    result["output_project"]["unchanged"] = (hash_depois == hash_antes)
    journal.record({"event": "build_observed",
                    "message_count": len(mensagens),
                    "message_count_from_build": len(do_build),
                    "messages_available": disponivel,
                    "output_sha256_after": hash_depois})
    if erro_depois:
        result["problems"].append(
            "sha256 do output apos o build ilegivel: %s" % erro_depois)
        return finish(STATUS_OUTPUT_MODIFIED_BY_BUILD)
    if hash_depois != hash_antes:
        result["problems"].append(
            "o arquivo de saida MUDOU durante o build (%r -> %r). Nenhum save "
            "foi chamado por este probe." % (hash_antes, hash_depois))
        return finish(STATUS_OUTPUT_MODIFIED_BY_BUILD)

    # Classifica pelo que o BUILD produziu. Passar a lista inteira faria o
    # veredito depender do banner do proprio probe.
    status = classify_build_outcome(do_build, disponivel)
    if status == STATUS_BUILD_FAILED:
        resumo = result["message_summary"]
        result["problems"].append(
            "build reportou %d erro(s); %d aviso(s) registrados na integra"
            % (resumo.get(SEVERITY_ERROR), resumo.get(SEVERITY_WARNING)))
    elif status == STATUS_MESSAGES_UNAVAILABLE:
        result["problems"].append(
            "build nao levantou, mas nenhuma mensagem pode ser coletada. "
            "'sem erro' nao pode ser afirmado sem ter lido mensagem alguma.")
    elif status == STATUS_SEVERITY_UNCLASSIFIED:
        result["problems"].append(
            "ha mensagem cuja severidade nao casa com a tabela literal; "
            "severidade desconhecida nao e tratada como aviso")
    return finish(status)


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
        "output_project_path": result.get("output_project", {}).get("path"),
        "output_sha256_before_build":
            result.get("output_project", {}).get("sha256_before_build"),
        "output_sha256_after_build":
            result.get("output_project", {}).get("sha256_after_build"),
        "output_unchanged_by_build":
            result.get("output_project", {}).get("unchanged"),
        "operations_requested": result.get("operations_requested"),
        "operations_authorized": result.get("operations_authorized"),
        "operations_executed": result.get("operations_executed"),
        "messages_available": result.get("messages_available"),
        # `message_summary` conta so o que o BUILD produziu; e ele que decide o
        # status. Os tres campos seguintes tornam o desconto AUDITAVEL --
        # quantas mensagens ja estavam no armazem, quantas sobraram, e como
        # ficaria a conta sem descontar nada. Desconto que nao aparece no
        # artefato e desconto que ninguem confere.
        "message_summary": result.get("message_summary"),
        "message_summary_including_pre_existing":
            result.get("message_summary_including_pre_existing"),
        "message_count": len(result.get("messages") or []),
        "message_count_total": result.get("message_count_total"),
        "message_count_from_build": result.get("message_count_from_build"),
        "messages_baseline_count": result.get("messages_baseline_count"),
        "messages_baseline_available": result.get("messages_baseline_available"),
        "blocks_promotion": result.get("blocks_promotion"),
        "errors": result.get("problems"),
        "gap_notes": result.get("gap_notes"),
        "no_other_mutator_requested":
            tuple(result.get("operations_requested") or ()) in
            ((), (EXECUTED_OPERATION,)),
        "generated_at": result.get("finished_at"),
    }


def build_report_markdown(result):
    resumo = result.get("message_summary") or {}
    lines = [
        "# Probe 40 -- W1.4: build do arquivo salvo (abertura separada)",
        "",
        "- status: **%s**" % result.get("status"),
        "- exit_code logico: **%s**" % result.get("exit_code"),
        "- fase observada: `%s`" % result.get("phase_observed"),
        "- projeto aberto: `%s`" % result.get("opened_project"),
        "- sha256 antes do build: `%s`"
        % result.get("output_project", {}).get("sha256_before_build"),
        "- sha256 depois do build: `%s`"
        % result.get("output_project", {}).get("sha256_after_build"),
        "- arquivo inalterado pelo build: **%s**"
        % result.get("output_project", {}).get("unchanged"),
        "",
        "## Mensagens de compilacao",
        "",
        "- fonte disponivel: **%s**" % result.get("messages_available"),
        "- erros: `%s`" % resumo.get(SEVERITY_ERROR),
        "- avisos: `%s`  (AVISO NAO E ERRO -- registrados na integra abaixo)"
        % resumo.get(SEVERITY_WARNING),
        "- informativos: `%s`" % resumo.get(SEVERITY_INFORMATION),
        "- nao classificados: `%s`" % resumo.get(SEVERITY_UNCLASSIFIED),
        "",
    ]
    for mensagem in result.get("messages") or []:
        lines.append("- [%s] %s (posicao: %s, objeto: %s)"
                     % (mensagem.get("severity"), mensagem.get("text"),
                        mensagem.get("position"), mensagem.get("object")))
    if not (result.get("messages") or []):
        lines.append("- nenhuma mensagem coletada")
    lines.extend(["", "## Lacunas", ""])
    for nota in result.get("gap_notes") or []:
        lines.append("- %s" % nota)
    if not (result.get("gap_notes") or []):
        lines.append("- nenhuma")
    lines.extend(["", "## Problemas", ""])
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

    manifest = {}
    for key in result:
        if key in ("journal",):
            continue
        manifest[key] = result[key]
    manifest["artifact_names"] = list(ARTIFACT_NAMES)
    manifest["volatile_fields"] = list(VOLATILE_FIELDS)
    manifest["exit_code_by_status"] = EXIT_BY_STATUS

    file_io.write_json(os.path.join(artifacts_dir, "build-manifest.json"), manifest)
    written.append("build-manifest.json")
    file_io.write_json(os.path.join(artifacts_dir, "build-messages.json"),
                       {"messages": result.get("messages") or [],
                        "summary": result.get("message_summary") or {},
                        "available": result.get("messages_available"),
                        "gap_notes": result.get("gap_notes") or []})
    written.append("build-messages.json")
    file_io.write_text(os.path.join(artifacts_dir, "build-report.md"),
                       build_report_markdown(result))
    written.append("build-report.md")
    file_io.write_json(os.path.join(artifacts_dir, "build-completion.json"),
                       build_completion(result))
    written.append("build-completion.json")
    return written


def main(script_globals=None):
    if script_globals is None:
        script_globals = globals()
    print("=" * 68)
    print("[INFO] probes/%s -- W1.4 build (escrita controlada)" % SCRIPT_NAME)
    print("=" * 68)

    if not _FILE_AVAILABLE:
        print("[FATAL] __file__ indisponivel")
        return EXIT_BY_STATUS[STATUS_FATAL]

    from common import file_io, probe_cli, project_access, safety

    try:
        result = run_build(script_globals, list(sys.argv or []), safety,
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

    print("[INFO] status=%s" % result.get("status"))
    print("[INFO] mensagens coletadas: %s" % len(result.get("messages") or []))
    for problem in result.get("problems") or []:
        print("[PROBLEM] %s" % problem)
    print("=" * 68)

    # ENCERRA O MASTERTOOL, e so DEPOIS de os artefatos estarem no disco.
    #
    # `CloseMainWindow()` nao serve nesta fase: compilar deixa o projeto
    # "alterado" em memoria, entao o pedido de fechar cai num dialogo modal de
    # salvar e a janela NUNCA fecha sozinha -- medido tres vezes seguidas na
    # run-019, com o operador tendo de clicar "Nao" em cada uma.
    #
    # `system.exit()` "shuts down the engine and exits the process"
    # (ScriptSystem.pyi L143-157) -- encerra sem passar pelo dialogo, porque
    # nao ha pedido de fechamento de janela a ser respondido.
    #
    # NAO E `Stop-Process` disfarcado: aquilo mata o processo de fora e pode
    # interromper gravacao de artefato; isto e o proprio produto se encerrando,
    # por API documentada, com os artefatos JA gravados acima.
    _encerrar_plataforma(script_globals)
    return result.get("exit_code")


def _encerrar_plataforma(script_globals):
    """Chama `system.exit(0)` se o global existir. Nunca levanta.

    O codigo de saida do probe ja foi decidido e gravado no artefato; este
    encerramento e sobre a JANELA, e nao sobre o veredito. Passar o exit_code
    aqui confundiria as duas coisas -- e o launcher, por contrato, nunca
    decide nada pelo exit code.
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
        print("[INFO] system.exit falhou (%r): feche a janela manualmente." % (exc,))


if "projects" in globals():
    sys.exit(main())

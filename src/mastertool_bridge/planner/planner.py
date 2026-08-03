"""Planner declarativo: `project_spec` -> plano de autoria literal.

Camada HOST (CPython 3), 100% offline. Nada aqui abre o MasterTool, importa
IronPython, executa processo, toca disco ou faz rede. O produto deste módulo é
**dado**: um dicionário JSON-serializável que descreve, passo a passo e em
ordem determinística, o que uma sessão de escrita controlada teria de fazer.

Pipeline
--------

    project_spec
      -> validação offline (mastertool_bridge.spec.validator + checagens
         próprias deste módulo)
      -> grafo de dependências (todas as famílias, não só FB/FUNCTION)
      -> ordenação topológica determinística
      -> plano de autoria literal (`steps`)
      -> expected tree / expected diff
      -> manifesto (hashes + allowlist derivada)

A restrição que decide o desenho
--------------------------------

**O planner produz DADOS; o executor tem chamadas LITERAIS.** O executor nunca
escolhe método por string: ele faz

    if operation == "replace":
        ...
    elif operation == "save_as":
        ...

e nada mais. Consequência direta, e não acidental, deste módulo:

  * `operation` é valor de um conjunto FECHADO e pequeno (`PLAN_OPERATIONS`),
    declarado como tupla de literais no topo do arquivo;
  * cada operação tem uma entrada correspondente em `EXECUTOR_CONTRACT`, que
    diz qual API mutável do MasterTool ela consome e se ela muta o projeto;
  * `tests/unit/test_planner.py` congela a tupla inteira num literal próprio,
    de modo que **acrescentar uma operação obriga a editar o teste e o
    contrato do executor**. Um conjunto que pudesse crescer sozinho seria um
    executor que aceitaria uma operação que ninguém escreveu — exatamente o
    dispatch dinâmico que este desenho recusa.

Não há `getattr`, `eval`, `exec`, dispatch por dicionário de funções nem
qualquer construção de nome de operação a partir de dados: os nomes só entram
no plano por referência às constantes `OPERATION_*`.

O plano não carrega texto final
-------------------------------

Herdado de `probes/32_edit_gvl_w1_3a.py` ("um plano que carregasse o texto
final autorizaria a si mesmo a escrever qualquer coisa"): cada passo de
`replace` carrega apenas o **hash** do texto planejado e um `source_location`
qualificado por nome (`function_blocks:FB_X:implementation`). O texto vem do
`project_spec`, cujo hash inteiro está preso no plano em `spec_sha256`. O
executor lê o texto da spec, confere o hash contra o passo, e só então escreve.
Plano e conteúdo ficam em artefatos separados, amarrados por hash.

Determinismo
------------

A mesma spec produz o mesmo plano byte a byte. Nenhum campo vem do relógio,
do sistema de arquivos, do ambiente ou de iteração de `set`/`dict` sem chave
explícita. O empate na ordenação topológica é resolvido pela chave
`(rank da família, nome)`, e o nome é comparado por ponto de código Unicode —
nomes IEC já são validados como `[A-Za-z_][A-Za-z0-9_]*`, portanto ASCII puro,
o que torna a comparação idêntica em qualquer plataforma, locale ou versão de
Python. Efeito colateral desejado: o plano é **invariante a permutação** das
listas da spec (mudar a ordem em que o autor escreveu `duts` não muda o plano,
só `spec_sha256`).

Normalização textual
--------------------

`normalize_authoring_text` reproduz, com a mesma semântica congelada, a regra
de `scripts/mastertool/common/authoring_text.normalize_text` (CRLF ≡ LF;
espaço em branco no fim de cada linha ignorado; UMA quebra final ignorada;
qualquer outra diferença é divergência). Ela é reescrita aqui, e não importada,
porque `scripts/mastertool/` é árvore IronPython não empacotada e importá-la de
`src/` acoplaria a camada host a um caminho que não existe numa instalação. A
proteção contra deriva não é confiança: `test_planner.py` compara as duas
implementações caractere a caractere sobre um corpus adversarial.

Este módulo NUNCA levanta. `None`, `[]`, `"x"`, `3`, `True`, dict malformado em
qualquer nível — tudo devolve `PlanResult` com `problems` preenchido e
`plan=None`.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass, field
from typing import Any

from mastertool_bridge.spec.validator import (
    _explain_invalid_name,
    _is_valid_iec_name,
    validate_project_spec,
)

# Reaproveitado do validador em vez de reescrito: duas expressões para o mesmo
# formato divergiriam, e a que envelheceria seria a cópia.
_SHA256_RE = re.compile(r"^[0-9a-fA-F]{64}$")

# Versão do contrato DESTE artefato. Família inteira da camada `src/`
# (docs/19 §7) — nunca a string "1.0" dos artefatos de probe/export.
PLAN_SCHEMA_VERSION = 1

PLAN_KIND = "authoring_plan"

# --- o conjunto FECHADO de operações -----------------------------------------
#
# Doze nomes. Cada um existe porque o executor tem um ramo `if operation ==`
# escrito à mão para ele. Acrescentar um nome aqui sem escrever o ramo
# correspondente é o defeito que `EXECUTOR_CONTRACT` e o literal congelado em
# `tests/unit/test_planner.py` existem para impedir.

OPERATION_CREATE_DUT = "create_dut"
OPERATION_CREATE_GVL = "create_gvl"
OPERATION_CREATE_FUNCTION = "create_function"
OPERATION_CREATE_FUNCTION_BLOCK = "create_function_block"
OPERATION_CREATE_PROGRAM = "create_program"
OPERATION_CREATE_TASK = "create_task"
OPERATION_CREATE_PROGRAM_CALL = "create_program_call"
OPERATION_BIND_PROGRAM_TO_TASK = "bind_program_to_task"
OPERATION_CONFIGURE_TASK = "configure_task"
OPERATION_REPLACE = "replace"
OPERATION_SAVE_AS = "save_as"
OPERATION_REOPEN = "reopen"
OPERATION_BUILD = "build"
OPERATION_VERIFY = "verify"

PLAN_OPERATIONS = (
    OPERATION_CREATE_DUT,
    OPERATION_CREATE_GVL,
    OPERATION_CREATE_FUNCTION,
    OPERATION_CREATE_FUNCTION_BLOCK,
    OPERATION_CREATE_PROGRAM,
    OPERATION_CREATE_TASK,
    OPERATION_CREATE_PROGRAM_CALL,
    OPERATION_BIND_PROGRAM_TO_TASK,
    OPERATION_CONFIGURE_TASK,
    OPERATION_REPLACE,
    OPERATION_SAVE_AS,
    OPERATION_REOPEN,
    OPERATION_BUILD,
    OPERATION_VERIFY,
)

# A task do Perfil de Projeto, tal como vem no `TemplateExemplo v1.project`. O nome é
# LITERAL porque a convenção do fabricante é por nome: o aviso de W2 (docs/41
# §1) cita `MainTask` e as quatro POUs do perfil textualmente.
PROFILE_TASK_NAME = "MainTask"

# Contrato que o executor precisa honrar, operação por operação.
#
# `mastertool_operation` é o nome EXATO da API mutável, tal como catalogado em
# `scripts/mastertool/common/safety.py::MASTERTOOL_MUTATING_OPERATIONS`
# (registro literal de docs/27 §7). `None` significa uma de duas coisas, e
# `cataloged` distingue qual:
#
#   mutating=False, cataloged=True  -> passo que não muta nada (reopen/verify);
#                                      não entra em allowlist nenhuma.
#   mutating=True,  cataloged=False -> a operação MUTA, mas a API que a realiza
#                                      NÃO está catalogada. Fail-closed: o
#                                      plano vira `executable=False` e registra
#                                      uma lacuna de medição. Inventar o nome
#                                      da API aqui seria inventar MasterTool.
# TRÊS COLUNAS, e não duas, porque `cataloged` responde uma pergunta mais
# fraca do que parecia responder.
#
#   `cataloged`     a API existe no registro literal de docs/27 §7.
#   `field_proven`  a operação foi EXERCIDA contra o produto real, dentro de
#                   uma cadeia que persistiu (`save_as`) e compilou (`build`),
#                   com artefato de execução citado.
#
# A distinção apareceu medindo: uma spec com um FUNCTION_BLOCK saía com
# `executable: True` e `create_function_block` na allowlist. A API está mesmo
# catalogada — mas W1.5 só a exerceu para LER o texto de nascimento e descartar
# a cópia SEM salvar. Nada nunca provou que um FB sobrevive a `save_as` e
# compila. "A API existe" e "a operação funciona na cadeia" são afirmações
# diferentes, e tratá-las como uma só é fail-OPEN: o plano prometeria executar
# o que ninguém executou.
EXECUTOR_CONTRACT = {
    # PROVADO na `run-033` (`docs/46`). `ST_EIXO` (STRUCT) e `EN_ESTADO`
    # (ENUM) criados, persistidos e compilados, com um PROGRAM que DECLARA uma
    # variável de cada — o compilador só diz algo sobre um DUT se alguém o
    # declarar.
    #
    # Ele esteve bloqueado desde `docs/35` por uma afirmação minha que se
    # provou errada: *"os valores do enum `DutType` não estão catalogados"*.
    # Estavam, no stub que o produto instala, e a `run-031` (`docs/45`) mediu
    # que o enum é injetado no escopo do script.
    OPERATION_CREATE_DUT: {
        "mastertool_operation": "create_dut", "mutating": True,
        "cataloged": True, "field_proven": True,
        "evidence": "docs/46 (W6, run-033)"},
    OPERATION_CREATE_GVL: {
        "mastertool_operation": "create_gvl", "mutating": True,
        "cataloged": True, "field_proven": True,
        "evidence": "docs/33 (W1.1), docs/37 (W1.4, run-019)"},
    # PROVADAS na `run-028` (`docs/43`), e a prova é conclusiva porque o
    # PROGRAM gerado **instancia** o FB e **chama** a FUNCTION: criar os dois e
    # deixá-los soltos provaria que a API cria objeto, não que o objeto serve.
    # Um nascimento quebrado teria reprovado no `Typify code`.
    #
    # Até a `run-028` as duas eram `field_proven: False` — W1.5 (`docs/35`) as
    # criou apenas para LER o texto de nascimento e descartar a cópia SEM
    # salvar. A diferença entre aquilo e isto é a cadeia completa:
    # `create` → `replace` → `save_as` → reabrir → `build`.
    OPERATION_CREATE_FUNCTION: {
        "mastertool_operation": "create_function", "mutating": True,
        "cataloged": True, "field_proven": True,
        "evidence": "docs/43 (W5, run-028)"},
    OPERATION_CREATE_FUNCTION_BLOCK: {
        "mastertool_operation": "create_function_block", "mutating": True,
        "cataloged": True, "field_proven": True,
        "evidence": "docs/43 (W5, run-028)"},
    OPERATION_CREATE_PROGRAM: {
        "mastertool_operation": "create_program", "mutating": True,
        "cataloged": True, "field_proven": True,
        "evidence": "docs/30 (W1.2), docs/37 (W1.4, run-019)"},
    # PROVADO na `run-036`, e o caminho até aqui é a história de duas medições.
    #
    # A `run-032` criou a task e o build passou com **zero erros** — e com um
    # aviso: *"No POU is defined for task 'TaskDiagnostico'"*. Uma task vazia
    # não é um projeto limpo, e por isso aquela execução não provou nada.
    #
    # Enchê-la NÃO se faz pela chamada idiomática: `UserPrg` roda pela cadeia da
    # `MainTask` (`docs/41`), e escrever ali uma chamada que a spec pediu para
    # outra task ligaria o programa ao ciclo errado — compilando limpo, e
    # errado. O executor recusa isso explicitamente.
    #
    # A `run-036` fez pelo caminho certo (`OPERATION_BIND_PROGRAM_TO_TASK`) e o
    # aviso SUMIU: 0 erros, 0 avisos. E a saída reaberta foi medida — a task
    # existe, com `PRG_DIAG` na posição 0 da lista dela. As duas coisas juntas,
    # porque "0 avisos" sozinho é ambíguo: uma task que tivesse sumido no
    # `save_as` também não avisaria nada.
    OPERATION_CREATE_TASK: {
        "mastertool_operation": "create_task", "mutating": True,
        "cataloged": True, "field_proven": True,
        "evidence": "docs/48 (W8, run-036)"},
    # PROGRAM CALL, IDIOMÁTICO. Duas formas foram medidas, e elas não empatam:
    #
    #   W2 (docs/39, run-021)  `MainTask.pous.add(nome)` -> compila, e o
    #                          FABRICANTE avisa que o padrão é outro.
    #   W3 (docs/41, run-026)  a chamada dentro de `UserPrg`, POU do Perfil de
    #                          Projeto -> compila com ZERO avisos.
    #
    # O planner emite a forma IDIOMÁTICA, e por isso a API consumida é
    # `replace` — não `add`. Uma fábrica que gerasse o caminho de W2 produziria
    # em escala exatamente o que o fabricante desaconselha.
    OPERATION_CREATE_PROGRAM_CALL: {
        "mastertool_operation": "replace", "mutating": True,
        "cataloged": True, "field_proven": True,
        "evidence": "docs/41 (W3, run-026)"},
    # A OUTRA forma de vincular, e ela existe porque o aviso de W2 nomeia
    # `MainTask`:
    #
    #   *"A tarefa MainTask deveria conter apenas a chamada do programa
    #   MainPrg. Chamadas adicionais de outros programas devem ser realizadas a
    #   partir das POUs correspondentes do Perfil de Projeto"*
    #
    # O fabricante está falando da task DO PERFIL. Uma task criada pela spec não
    # é a `MainTask`, o perfil não diz nada sobre ela, e `UserPrg` — que roda
    # pela cadeia da `MainTask` — seria o caminho ERRADO para chegar nela.
    # Para essa, a lista de POUs da própria task é o único caminho que existe:
    # `ScriptPouObjectCollection.add(pou_name)`, o mesmo verbo `add` que W2
    # exerceu (docs/39) — outro RECEPTOR, mesma API.
    #
    # PROVADO na `run-036`, na mesma cadeia de `create_task` — as duas saíram
    # juntas da lista de operações em prova, porque uma task cheia é uma coisa
    # só e provar metade dela não provaria nada.
    #
    # O que a execução mediu, além do build limpo: a lista da task era `[]`
    # antes e `['PRG_DIAG']` depois, e a mesma lista foi relida do projeto
    # SALVO e REABERTO. O `add` que não acrescentasse nada passaria pelas duas
    # primeiras verificações e morreria nessa.
    OPERATION_BIND_PROGRAM_TO_TASK: {
        "mastertool_operation": "add", "mutating": True,
        "cataloged": True, "field_proven": True,
        "evidence": "docs/48 (W8, run-036)"},
    # A CLASSE DE MUTAÇÃO NOVA: atribuição de propriedade, e não chamada de
    # método. `docs/48` §5 nomeou o buraco — a task criada nasce `t#20ms` com
    # prioridade `1`, mais rápida e mais prioritária que a `MainTask`, e a
    # fábrica não sabia mudar isso.
    #
    # `mastertool_operation` é `None` aqui de propósito: esta operação NÃO
    # consome uma API do registro de métodos. O que ela consome está em
    # `MASTERTOOL_PROPERTY_WRITES`, com prefixo `set:`, e a allowlist derivada
    # a pega de `task_properties` — uma entrada por propriedade escrita, e não
    # um nome só que autorizasse as quatro de uma vez.
    #
    # PROVADA na `run-037`. As quatro escritas foram relidas do objeto logo
    # após a atribuição, e depois de novo do projeto SALVO e REABERTO:
    # `t#20ms` → `t#500ms`, prioridade `1` → `25`. A `MainTask` ficou
    # intacta (100 ms, prioridade 13), que é o que prova que a escrita foi na
    # task certa e não em "uma task".
    OPERATION_CONFIGURE_TASK: {
        "mastertool_operation": None, "mutating": True,
        "cataloged": True, "field_proven": True,
        "evidence": "docs/49 (W9, run-037)"},
    OPERATION_REPLACE: {
        "mastertool_operation": "replace", "mutating": True,
        "cataloged": True, "field_proven": True,
        "evidence": "docs/33 (W1.3A), docs/34 (W1.3B), docs/37 (W1.4)"},
    OPERATION_SAVE_AS: {
        "mastertool_operation": "save_as", "mutating": True,
        "cataloged": True, "field_proven": True,
        "evidence": "docs/33, docs/37, docs/39, docs/41"},
    # Reabrir é abrir um projeto — leitura, não mutação. Fica no plano porque
    # a ordem canônica exige que a verificação aconteça numa sessão nova
    # (docs/32 §3: "é o que distingue 'existiu na sessão' de 'foi persistido'").
    OPERATION_REOPEN: {
        "mastertool_operation": None, "mutating": False,
        "cataloged": True, "field_proven": True,
        "evidence": "docs/37 (postsave), docs/41"},
    OPERATION_BUILD: {
        "mastertool_operation": "build", "mutating": True,
        "cataloged": True, "field_proven": True,
        "evidence": "docs/37 (run-019), docs/39 (run-021), docs/41 (run-026)"},
    OPERATION_VERIFY: {
        "mastertool_operation": None, "mutating": False,
        "cataloged": True, "field_proven": True,
        "evidence": "docs/37, docs/41"},
}

# --- alvos ------------------------------------------------------------------

TARGET_KIND_DUT = "dut"
TARGET_KIND_GVL = "gvl"
TARGET_KIND_FUNCTION = "function"
TARGET_KIND_FUNCTION_BLOCK = "function_block"
TARGET_KIND_PROGRAM = "program"
TARGET_KIND_TASK = "task"
TARGET_KIND_PROGRAM_CALL = "program_call"
TARGET_KIND_DUT_DECLARATION = "dut_declaration"
TARGET_KIND_GVL_DECLARATION = "gvl_declaration"
TARGET_KIND_FUNCTION_DECLARATION = "function_declaration"
TARGET_KIND_FUNCTION_IMPLEMENTATION = "function_implementation"
TARGET_KIND_FUNCTION_BLOCK_DECLARATION = "function_block_declaration"
TARGET_KIND_FUNCTION_BLOCK_IMPLEMENTATION = "function_block_implementation"
TARGET_KIND_PROGRAM_DECLARATION = "program_declaration"
TARGET_KIND_PROGRAM_IMPLEMENTATION = "program_implementation"
TARGET_KIND_PROJECT = "project"

TARGET_KINDS = (
    TARGET_KIND_DUT,
    TARGET_KIND_GVL,
    TARGET_KIND_FUNCTION,
    TARGET_KIND_FUNCTION_BLOCK,
    TARGET_KIND_PROGRAM,
    TARGET_KIND_TASK,
    TARGET_KIND_PROGRAM_CALL,
    TARGET_KIND_DUT_DECLARATION,
    TARGET_KIND_GVL_DECLARATION,
    TARGET_KIND_FUNCTION_DECLARATION,
    TARGET_KIND_FUNCTION_IMPLEMENTATION,
    TARGET_KIND_FUNCTION_BLOCK_DECLARATION,
    TARGET_KIND_FUNCTION_BLOCK_IMPLEMENTATION,
    TARGET_KIND_PROGRAM_DECLARATION,
    TARGET_KIND_PROGRAM_IMPLEMENTATION,
    TARGET_KIND_PROJECT,
)

# Nome de alvo dos passos de nível de projeto. Contém '$', que o regex de nome
# IEC do validador (`[A-Za-z_][A-Za-z0-9_]*`) torna impossível — não há como
# colidir com um objeto real da spec.
PROJECT_TARGET = "$project"

# --- procedência do texto ANTERIOR a um `replace` ----------------------------
#
# `created_in_this_plan`: o objeto foi criado por um passo ANTERIOR deste mesmo
# plano, e o texto que o MasterTool gera logo após `create_*` (o esqueleto) NÃO
# está medido para DUT/FUNCTION/FUNCTION_BLOCK/PROGRAM — só a GVL de W1.1 teve
# o seu medido (docs/29). Por isso `expected_before_sha256` é `None` e o passo
# carrega `created_by_sequence`: o executor prova que está sobrescrevendo um
# objeto que ele mesmo acabou de criar, nunca um preexistente. Declarar um hash
# inventado aqui seria pior que declarar `None`.
EXPECTED_BEFORE_CREATED_IN_THIS_PLAN = "created_in_this_plan"
EXPECTED_BEFORE_NOT_APPLICABLE = "not_applicable"

# `measured`: o objeto JÁ EXISTIA no projeto, e o texto atual dele foi MEDIDO
# por uma leitura read-only anterior. É a procedência que a fase R2 exige, e a
# única que autoriza sobrescrever algo que este plano não criou.
#
# A diferença com `created_in_this_plan` não é de grau: lá o executor prova que
# está sobrescrevendo um objeto que ele mesmo acabou de criar — o conteúdo
# anterior é um esqueleto que o produto gerou, e não interessa a ninguém. Aqui
# o conteúdo anterior é trabalho de engenharia de outra pessoa, e sobrescrevê-lo
# sem conferir o que estava lá é a diferença entre alteração transacional e
# escrita cega.
#
# O hash NÃO é declarado pelo autor da spec de cabeça: ele vem de um artefato
# de leitura, e a spec o repete. Se o objeto mudou entre a medição e a
# execução, os dois divergem e o executor recusa — que é exatamente o caso que
# esta procedência existe para pegar.
EXPECTED_BEFORE_MEASURED = "measured"

EXPECTED_BEFORE_KINDS = (
    EXPECTED_BEFORE_CREATED_IN_THIS_PLAN,
    EXPECTED_BEFORE_NOT_APPLICABLE,
    EXPECTED_BEFORE_MEASURED,
)

# --- lacunas de medição ------------------------------------------------------

GAP_UNCATALOGED_MASTERTOOL_OPERATION = "uncataloged_mastertool_operation"
# API catalogada mas NUNCA exercida numa cadeia que persistiu e compilou.
GAP_OPERATION_NOT_FIELD_PROVEN = "operation_not_field_proven"
GAP_UNMEASURED_LANGUAGE_GUID = "unmeasured_language_guid"
# Vincular programa a uma task que o plano NÃO cria e que não é a do perfil.
GAP_UNMEASURED_TASK_BINDING = "unmeasured_task_binding"

MEASUREMENT_GAP_KINDS = (
    GAP_UNCATALOGED_MASTERTOOL_OPERATION,
    GAP_OPERATION_NOT_FIELD_PROVEN,
    GAP_UNMEASURED_LANGUAGE_GUID,
    GAP_UNMEASURED_TASK_BINDING,
)

# GUID da linguagem ST, único MEDIDO em runtime (probe 29, docs/30). Qualquer
# outro GUID no `project_spec` é sintaticamente aceitável e semanticamente não
# medido — vira lacuna, não erro.
MEASURED_LANGUAGE_GUIDS = ("cc393387-a21c-4f68-a3e3-84c36951965d",)

# --- limites de VERIFICAÇÃO --------------------------------------------------
#
# Diferentes das lacunas de medição: uma lacuna impede EXECUTAR; um limite
# abaixo não impede nada, mas delimita o que o passo `verify` pode honestamente
# afirmar. Estão no plano, e não só num comentário, porque quem lê o artefato
# depois precisa saber o que "verificado" NÃO cobriu — um verificador que
# alegasse mais do que a API permite medir seria pior que um que alega menos.
#
# LIMIT_LANGUAGE_NOT_READABLE: medido hoje — não existe API catalogada para LER
#   a linguagem de um objeto já existente. `language_guid` no plano é PARÂMETRO
#   DE ENTRADA de `create_*` (o `Nullable<Guid>` de docs/30), nunca um valor a
#   reconferir depois. Por isso este módulo não tem — e não pode ter —
#   comparação entre linguagem declarada e linguagem observada: seria uma
#   validação inverificável.
# LIMIT_DIRECT_CHILDREN_ONLY: a varredura dos probes usa `get_children(False)`,
#   isto é, SÓ FILHOS DIRETOS. `expected_tree.persistent_additions` é por isso
#   uma lista de um único nível, do container IEC (a Application) — o planner
#   nunca emite `create_folder` e nunca aninha objeto em objeto, exatamente
#   para que a lista seja comparável com o que o verificador consegue medir.
# LIMIT_TASK_CONTAINER_SEPARATE: tasks vivem na Task Configuration e Program
#   Calls são filhas de uma task — nenhuma das duas aparece num
#   `get_children(False)` da Application. Ficam em listas SEPARADAS de
#   `expected_tree` por isso, e não por organização estética: somá-las a
#   `persistent_additions` faria o diff estrutural acusar ausência de objetos
#   que o verificador jamais veria naquele container.
LIMIT_LANGUAGE_NOT_READABLE = "language_not_readable"
LIMIT_DIRECT_CHILDREN_ONLY = "direct_children_only"
LIMIT_TASK_CONTAINER_SEPARATE = "task_container_not_in_application_scan"

VERIFICATION_LIMIT_KINDS = (
    LIMIT_LANGUAGE_NOT_READABLE,
    LIMIT_DIRECT_CHILDREN_ONLY,
    LIMIT_TASK_CONTAINER_SEPARATE,
)

# --- ordem canônica ----------------------------------------------------------
#
# DUTs -> GVLs -> FUNCTIONs -> FUNCTION_BLOCKs -> PROGRAMs, e depois tasks,
# program calls, save_as, reopen, build, verify. É a mesma ordem de
# `spec/validator.py::_CREATION_FAMILY_ORDER`, e o rank abaixo é o componente
# MAIOR da chave de ordenação topológica: nenhuma GVL é criada antes de todos
# os DUTs, mesmo que a GVL não dependa de nenhum deles.
OBJECT_FAMILIES = ("duts", "gvls", "functions", "function_blocks", "programs")

FAMILY_RANK = {family: rank for rank, family in enumerate(OBJECT_FAMILIES)}

# Campos de texto por família, na ordem em que os `replace` são emitidos:
# declaração antes de implementação, sempre.
TEXT_FIELDS_BY_FAMILY = {
    "duts": ("declaration",),
    "gvls": ("declaration",),
    "functions": ("declaration", "implementation"),
    "function_blocks": ("declaration", "implementation"),
    "programs": ("declaration", "implementation"),
}

# Famílias que um `uses` pode alcançar, por família de origem. Espelha
# `spec/validator.py::_ALLOWED_USES_TARGETS` — a resolução de um nome usado
# procura só nestas famílias, na ordem canônica.
ALLOWED_USES_TARGETS = {
    "duts": ("duts",),
    "gvls": ("duts", "gvls"),
    "functions": ("duts", "gvls", "functions"),
    "function_blocks": ("duts", "gvls", "functions", "function_blocks"),
    "programs": ("duts", "gvls", "functions", "function_blocks"),
}


class PlannerError(ValueError):
    """Reservado para chamadores que queiram transformar `problems` em
    exceção. `build_authoring_plan` nunca a levanta."""


@dataclass
class PlanResult:
    """`problems` vazio é a ÚNICA condição de sucesso, e a única situação em
    que `plan` não é `None`. Um plano parcial seria pior que nenhum: ele
    pareceria executável."""

    problems: list[str] = field(default_factory=list)
    plan: dict | None = None

    @property
    def ok(self) -> bool:
        return not self.problems and self.plan is not None


# --- texto -------------------------------------------------------------------

def normalize_authoring_text(text: Any) -> str:
    """Regra congelada de normalização, idêntica em semântica a
    `scripts/mastertool/common/authoring_text.normalize_text`:

        CRLF e LF equivalentes
        espaço em branco no fim de cada linha ignorado
        UMA quebra de linha final ignorada
        qualquer outra diferença é DIVERGÊNCIA

    Nunca levanta: entrada que não é texto vira string vazia normalizada, e
    quem chama decide se isso é divergência.
    """
    if not isinstance(text, str):
        text = ""
    unified = text.replace("\r\n", "\n").replace("\r", "\n")
    lines = [line.rstrip(" \t\f\v") for line in unified.split("\n")]
    if len(lines) > 1 and lines[-1] == "":
        lines = lines[:-1]
    return "\n".join(lines)


def sha256_of_text(text: Any) -> str | None:
    """SHA-256 do texto BRUTO (sem normalizar), UTF-8. `None` para entrada que
    não é texto — deliberadamente do bruto, para que comparar bruto e
    normalizado lado a lado prove que uma divergência é só de fim de linha."""
    if not isinstance(text, str):
        return None
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def canonical_json(payload: Any) -> str:
    """Serialização canônica: chaves ordenadas, sem espaço supérfluo, UTF-8
    literal. É a forma sobre a qual todo hash deste módulo é calculado, para
    que "o mesmo plano" signifique "os mesmos bytes"."""
    return json.dumps(payload, sort_keys=True, ensure_ascii=False,
                      separators=(",", ":"))


def plan_to_json(plan: Any) -> str:
    """Forma legível e estável do plano, para gravar em arquivo. Também
    determinística: mesmas chaves, mesma ordem, mesma indentação."""
    return json.dumps(plan, sort_keys=True, ensure_ascii=False, indent=2) + "\n"


# --- grafo -------------------------------------------------------------------

def _node_key(family: str, name: str) -> str:
    """Chave qualificada por família, no mesmo formato que
    `ValidationResult.creation_order` já usa (`duts:ST_Motor`)."""
    return family + ":" + name


def _sort_key(family: str, name: str) -> tuple[int, str]:
    """A ÚNICA regra de desempate da ordenação topológica.

    Componente maior: o rank da família na ordem canônica. Componente menor: o
    nome, comparado por ponto de código Unicode. Nomes IEC válidos são
    `[A-Za-z_][A-Za-z0-9_]*`, ou seja ASCII puro — a comparação não depende de
    locale, de plataforma nem de versão de Python. Nenhuma iteração de `set` ou
    de `dict` participa da decisão de ordem em lugar nenhum deste módulo.
    """
    return (FAMILY_RANK[family], name)


def _canonical_cycle(cycle: list[str]) -> tuple[str, ...]:
    """Rotaciona o ciclo para começar pelo menor nó, e o fecha repetindo esse
    nó no fim. Dois percursos que descrevem o MESMO ciclo passam a ter a mesma
    representação, o que permite deduplicar sem perder o caminho."""
    body = cycle[:-1] if len(cycle) > 1 and cycle[0] == cycle[-1] else list(cycle)
    if not body:
        return ()
    start = body.index(min(body))
    rotated = body[start:] + body[:start]
    return tuple(rotated + [rotated[0]])


def _find_cycles(graph: dict[str, list[str]], order: list[str]) -> list[list[str]]:
    """Todos os ciclos alcançáveis do grafo de dependências, cada um com o
    CAMINHO completo (`A -> B -> C -> A`), não apenas "há ciclo".

    Busca em profundidade iterativa (sem recursão: uma spec grande com cadeia
    longa não pode estourar a pilha do interpretador), com nós e vizinhos
    percorridos em ordem de chave — o conjunto de ciclos reportados, e a ordem
    deles, são determinísticos.
    """
    white, gray, black = 0, 1, 2
    color = {node: white for node in order}
    cycles: list[list[str]] = []
    seen: set[tuple[str, ...]] = set()

    for root in order:
        if color[root] != white:
            continue
        color[root] = gray
        path = [root]
        stack = [(root, 0)]
        while stack:
            node, index = stack[-1]
            neighbors = graph.get(node, [])
            if index < len(neighbors):
                stack[-1] = (node, index + 1)
                neighbor = neighbors[index]
                if neighbor not in color:
                    continue
                if color[neighbor] == gray:
                    start = path.index(neighbor)
                    canonical = _canonical_cycle(path[start:] + [neighbor])
                    if canonical and canonical not in seen:
                        seen.add(canonical)
                        cycles.append(list(canonical))
                elif color[neighbor] == white:
                    color[neighbor] = gray
                    path.append(neighbor)
                    stack.append((neighbor, 0))
            else:
                stack.pop()
                color[node] = black
                path.pop()
    return cycles


def _topological_order(nodes: dict[str, tuple[str, str]],
                       graph: dict[str, list[str]]) -> list[str]:
    """Kahn com seleção do MENOR `_sort_key` entre os nós prontos.

    Por que Kahn com mínimo global, e não "uma topológica por família": o rank
    da família domina a chave, então um nó de família posterior só é escolhido
    quando NENHUM nó de família anterior está pronto. Como `uses` só aponta
    para a mesma família ou para famílias anteriores (regra do validador), sem
    ciclo sempre há um nó pronto na família mais antiga pendente — logo todos
    os DUTs saem antes de qualquer GVL, e assim por diante. A ordem canônica é
    consequência da chave, não um laço separado que poderia divergir dela.

    Pressupõe grafo acíclico; ciclos são reportados ANTES, por `_find_cycles`.
    """
    pending = {node: 0 for node in nodes}
    dependents: dict[str, list[str]] = {node: [] for node in nodes}
    for node in sorted(nodes, key=lambda key: _sort_key(*nodes[key])):
        for dependency in graph.get(node, []):
            if dependency in nodes:
                pending[node] += 1
                dependents[dependency].append(node)

    ready = sorted((node for node in nodes if pending[node] == 0),
                   key=lambda key: _sort_key(*nodes[key]))
    emitted: list[str] = []
    while ready:
        node = ready.pop(0)
        emitted.append(node)
        released = []
        for dependent in dependents[node]:
            pending[dependent] -= 1
            if pending[dependent] == 0:
                released.append(dependent)
        if released:
            ready.extend(released)
            ready.sort(key=lambda key: _sort_key(*nodes[key]))
    return emitted


# --- passos ------------------------------------------------------------------

def _step(sequence: int, operation: str, target_kind: str, target_name: str,
          source_location: str,
          expected_before_kind: str = EXPECTED_BEFORE_NOT_APPLICABLE,
          expected_before_sha256: str | None = None,
          planned_after_sha256: str | None = None,
          planned_after_normalized_sha256: str | None = None,
          language_guid: str | None = None,
          dut_kind: str | None = None,
          return_type: str | None = None,
          created_by_sequence: int | None = None,
          task_name: str | None = None,
          program_name: str | None = None,
          task_properties: list[dict] | None = None) -> dict:
    """Registro literal de UM passo. Formato UNIFORME: as mesmas quinze chaves
    em todo passo, `None` onde não se aplica.

    Uniforme de propósito. Um executor com chamadas literais lê chave por chave
    escrita no código; se a forma do registro variasse por operação, ele teria
    de descobrir quais chaves existem — que é dispatch dinâmico com outro nome.
    """
    return {
        "sequence": sequence,
        "operation": operation,
        "target_kind": target_kind,
        "target_name": target_name,
        "source_location": source_location,
        "expected_before_kind": expected_before_kind,
        "expected_before_sha256": expected_before_sha256,
        "planned_after_sha256": planned_after_sha256,
        "planned_after_normalized_sha256": planned_after_normalized_sha256,
        "language_guid": language_guid,
        "dut_kind": dut_kind,
        "return_type": return_type,
        "created_by_sequence": created_by_sequence,
        "task_name": task_name,
        "program_name": program_name,
        # Lista ORDENADA de {"property", "value"}. Lista, e não dicionário,
        # porque a ordem em que as propriedades são escritas é significativa:
        # o stub condiciona `interval` a `kind_of_task` já ser Cyclic, então
        # o tipo tem de ser escrito antes do intervalo. Um dicionário deixaria
        # essa ordem por conta da serialização.
        "task_properties": task_properties,
    }


# ORDEM LITERAL de escrita das propriedades de task, e não a ordem em que o
# autor da spec as escreveu.
#
# `kind_of_task` primeiro porque o stub condiciona `interval` a ele
# (L119-129: "Requires the property kind_of_task to be set to
# KindOfTask.Cyclic or KindOfTask.ExternalEvent"). `interval_unit` depois de
# `interval` pela mesma dependência declarada (L135-144). `priority` é
# independente e fecha a lista.
TASK_PROPERTY_ORDER = ("kind_of_task", "interval", "interval_unit", "priority")


def _task_properties_of(spec: dict, task_name: str) -> list[dict]:
    """As propriedades DECLARADAS de uma task, na ordem de escrita.

    Só entra o que a spec escreveu: ausente não vira default explícito. Quem
    não declara fica com o que o produto der, e `docs/48` §4 documenta o que
    isso significa — escrever um default nosso aqui esconderia a diferença
    entre "o autor pediu 20 ms" e "ninguém pediu nada".
    """
    tarefas = spec.get("tasks")
    if not isinstance(tarefas, list):
        return []
    for tarefa in tarefas:
        if not isinstance(tarefa, dict) or tarefa.get("name") != task_name:
            continue
        declaradas = []
        for propriedade in TASK_PROPERTY_ORDER:
            if propriedade not in tarefa:
                continue
            valor = tarefa[propriedade]
            if valor is None:
                continue
            # `priority` é `str` no stub e número na spec, e a conversão mora
            # AQUI, no plano — não no executor. O plano é o artefato auditável:
            # ele tem de mostrar o texto exato que vai ser escrito.
            if propriedade == "priority":
                valor = str(valor)
            declaradas.append({"property": propriedade, "value": valor})
        return declaradas
    return []


def _language_guid_of(obj: dict) -> str | None:
    language = obj.get("language")
    if isinstance(language, dict):
        guid = language.get("guid")
        if isinstance(guid, str):
            return guid
    return None


# --- validações próprias do planner ------------------------------------------

def _check_template(spec: dict, expected_template: Any,
                    problems: list[str]) -> None:
    """Confere o template declarado contra o template ESPERADO pelo chamador.

    Existe porque a spec declara em qual template ela se apoia, mas declarar
    não é provar: um plano gerado contra `TemplateExemplo-v1` e executado sobre outro
    arquivo produziria diff inexplicável. Comparação por igualdade, hex em
    minúsculas, sem tolerância.
    """
    if expected_template is None:
        return
    if not isinstance(expected_template, dict):
        problems.append(
            "expected_template deve ser um objeto {'id': ..., 'sha256': ...}, "
            f"recebido {type(expected_template).__name__}.")
        return
    template = spec.get("template")
    if not isinstance(template, dict):
        return  # já reportado pelo validador da spec
    declared_id = template.get("id")
    wanted_id = expected_template.get("id")
    if declared_id != wanted_id:
        problems.append(
            f"template.id declarado é {declared_id!r}, mas o plano foi pedido "
            f"contra {wanted_id!r} — planejar sobre outro template produziria "
            "um diff que ninguém consegue explicar.")
    declared_sha = template.get("sha256")
    wanted_sha = expected_template.get("sha256")
    declared_norm = declared_sha.lower() if isinstance(declared_sha, str) else declared_sha
    wanted_norm = wanted_sha.lower() if isinstance(wanted_sha, str) else wanted_sha
    if declared_norm != wanted_norm:
        problems.append(
            f"template.sha256 declarado é {declared_sha!r}, esperado "
            f"{wanted_sha!r} — o arquivo de template mudou, ou a spec aponta "
            "para outro.")


def _check_libraries(spec: dict, problems: list[str]) -> list[str]:
    """Bibliotecas são PRECONDIÇÃO, não mutação.

    DECISÃO deste slice: a ordem canônica do contrato (DUTs -> ... -> verify)
    não contém passo de biblioteca, e `add_library` existe no registro mas
    nunca foi exercido por nenhuma fase W1. Emitir `add_library` seria ampliar
    a superfície mutável por conveniência. Logo, as bibliotecas declaradas
    entram como precondição a CONFERIR no passo `verify`: o projeto tem de
    referenciá-las já; se não referenciar, quem resolve é um ato humano à
    parte, não este plano.
    """
    raw = spec.get("libraries", [])
    if not isinstance(raw, list):
        return []
    names: list[str] = []
    for item in raw:
        if isinstance(item, dict) and isinstance(item.get("name"), str):
            names.append(item["name"])
    duplicates = sorted({name for name in names if names.count(name) > 1})
    for name in duplicates:
        problems.append(
            f"libraries: biblioteca {name!r} declarada mais de uma vez — a "
            "precondição de biblioteca é um conjunto, repetir não a reforça.")
    return sorted(set(names))


def _check_program_calls(spec: dict, problems: list[str]) -> list[tuple[str, str]]:
    """Program Calls, e a única checagem que o validador da spec não faz:
    chamada repetida da MESMA task para o MESMO PROGRAM.

    Repetir a chamada não a executa duas vezes de forma útil — produz duas
    entradas idênticas na Task Configuration, que a verificação estrutural
    depois não consegue distinguir uma da outra.
    """
    raw = spec.get("tasks", [])
    if not isinstance(raw, list):
        return []
    pairs: list[tuple[str, str]] = []
    for task in raw:
        if not isinstance(task, dict):
            continue
        task_name = task.get("name")
        calls = task.get("program_calls")
        if not isinstance(task_name, str) or not isinstance(calls, list):
            continue
        seen: set[str] = set()
        for called in calls:
            if not isinstance(called, str):
                continue
            if called in seen:
                problems.append(
                    f"tasks.{task_name}.program_calls: {called!r} aparece mais "
                    "de uma vez na mesma task — duas chamadas idênticas ficam "
                    "indistinguíveis na verificação estrutural.")
                continue
            seen.add(called)
            pairs.append((task_name, called))
    # ORDEM DECLARADA, não alfabética.
    #
    # Estes pares viram passos do plano na ordem em que saem daqui, e o
    # executor escreve as chamadas nessa ordem. Em IEC, a ordem das chamadas
    # dentro de uma task É a ordem de execução no ciclo: alfabetizar aqui
    # produzia um programa que se comporta diferente do que a spec pediu, sem
    # nenhum diagnóstico — o modo de falha "silêncio virando sucesso" que este
    # projeto persegue. Uma spec com `["PRG_Bomba", "PRG_Alarme"]` executava
    # o alarme primeiro.
    #
    # Determinismo não se perde: a ordem da spec é tão determinística quanto a
    # alfabética, e agora é a ordem que o autor escreveu.
    return pairs


# --- construção do plano -----------------------------------------------------

def _collect_objects(spec: dict) -> dict[str, tuple[str, str]]:
    """{chave qualificada: (família, nome)} das cinco famílias de objeto."""
    nodes: dict[str, tuple[str, str]] = {}
    for family in OBJECT_FAMILIES:
        raw = spec.get(family, [])
        if not isinstance(raw, list):
            continue
        for item in raw:
            if not isinstance(item, dict):
                continue
            name = item.get("name")
            if isinstance(name, str) and name:
                nodes.setdefault(_node_key(family, name), (family, name))
    return nodes


def _object_by_key(spec: dict) -> dict[str, dict]:
    objects: dict[str, dict] = {}
    for family in OBJECT_FAMILIES:
        raw = spec.get(family, [])
        if not isinstance(raw, list):
            continue
        for item in raw:
            if not isinstance(item, dict):
                continue
            name = item.get("name")
            if isinstance(name, str) and name:
                objects.setdefault(_node_key(family, name), item)
    return objects


def _build_graph(nodes: dict[str, tuple[str, str]],
                 objects: dict[str, dict]) -> dict[str, list[str]]:
    """Arestas nó -> dependências, resolvendo cada nome de `uses` para a chave
    qualificada da família permitida em que ele existe.

    A resolução varre as famílias permitidas na ordem canônica e para na
    primeira ocorrência. Isso só é ambíguo quando há nome duplicado entre
    famílias — caso em que `problems` já está preenchido e nenhum plano é
    produzido, então a ambiguidade nunca chega ao plano.
    """
    graph: dict[str, list[str]] = {}
    for key in sorted(nodes, key=lambda item: _sort_key(*nodes[item])):
        family, _name = nodes[key]
        uses = objects.get(key, {}).get("uses")
        targets: list[str] = []
        if isinstance(uses, list):
            for used in uses:
                if not isinstance(used, str):
                    continue
                for candidate_family in ALLOWED_USES_TARGETS.get(family, ()):
                    candidate = _node_key(candidate_family, used)
                    if candidate in nodes:
                        if candidate not in targets:
                            targets.append(candidate)
                        break
        graph[key] = sorted(targets, key=lambda item: _sort_key(*nodes[item]))
    return graph


def _emit_create_steps(ordered: list[str], nodes: dict[str, tuple[str, str]],
                       objects: dict[str, dict], steps: list[dict],
                       create_sequence: dict[str, int]) -> None:
    """Fase 1: TODOS os `create_*`, na ordem topológica canônica.

    Criar tudo antes de escrever qualquer texto é o que docs/32 §3 mediu e
    justificou: a implementação de um objeto pode citar outro (`GVL_X.var`), e
    o texto só faz sentido depois que o objeto citado já existe na árvore em
    memória. O if/elif abaixo é literal, um ramo por família — a mesma forma
    que o executor terá.
    """
    for key in ordered:
        family, name = nodes[key]
        obj = objects.get(key, {})
        sequence = len(steps) + 1
        create_sequence[key] = sequence
        if family == "duts":
            kind = obj.get("kind")
            steps.append(_step(
                sequence, operation=OPERATION_CREATE_DUT,
                target_kind=TARGET_KIND_DUT, target_name=name,
                source_location=key,
                language_guid=_language_guid_of(obj),
                dut_kind=kind if isinstance(kind, str) else None))
        elif family == "gvls":
            steps.append(_step(
                sequence, operation=OPERATION_CREATE_GVL,
                target_kind=TARGET_KIND_GVL, target_name=name,
                source_location=key,
                language_guid=_language_guid_of(obj)))
        elif family == "functions":
            return_type = obj.get("return_type")
            steps.append(_step(
                sequence, operation=OPERATION_CREATE_FUNCTION,
                target_kind=TARGET_KIND_FUNCTION, target_name=name,
                source_location=key,
                language_guid=_language_guid_of(obj),
                return_type=return_type if isinstance(return_type, str) else None))
        elif family == "function_blocks":
            steps.append(_step(
                sequence, operation=OPERATION_CREATE_FUNCTION_BLOCK,
                target_kind=TARGET_KIND_FUNCTION_BLOCK, target_name=name,
                source_location=key,
                language_guid=_language_guid_of(obj)))
        elif family == "programs":
            steps.append(_step(
                sequence, operation=OPERATION_CREATE_PROGRAM,
                target_kind=TARGET_KIND_PROGRAM, target_name=name,
                source_location=key,
                language_guid=_language_guid_of(obj)))


def _replace_target_kind(family: str, text_field: str) -> str:
    """Família + campo -> `target_kind`, por if/elif literal. Sem concatenar
    `family + "_" + text_field`: um `target_kind` construído a partir de dados
    poderia produzir um valor fora do conjunto fechado sem que nada reclamasse.
    """
    if family == "duts" and text_field == "declaration":
        return TARGET_KIND_DUT_DECLARATION
    if family == "gvls" and text_field == "declaration":
        return TARGET_KIND_GVL_DECLARATION
    if family == "functions" and text_field == "declaration":
        return TARGET_KIND_FUNCTION_DECLARATION
    if family == "functions" and text_field == "implementation":
        return TARGET_KIND_FUNCTION_IMPLEMENTATION
    if family == "function_blocks" and text_field == "declaration":
        return TARGET_KIND_FUNCTION_BLOCK_DECLARATION
    if family == "function_blocks" and text_field == "implementation":
        return TARGET_KIND_FUNCTION_BLOCK_IMPLEMENTATION
    if family == "programs" and text_field == "declaration":
        return TARGET_KIND_PROGRAM_DECLARATION
    if family == "programs" and text_field == "implementation":
        return TARGET_KIND_PROGRAM_IMPLEMENTATION
    return ""


def _emit_replace_steps(ordered: list[str], nodes: dict[str, tuple[str, str]],
                        objects: dict[str, dict], steps: list[dict],
                        create_sequence: dict[str, int],
                        text_hashes: dict[str, dict]) -> list[str]:
    """Fase 2: os `replace`, na MESMA ordem de objeto da fase 1, declaração
    antes de implementação."""
    replaced: list[str] = []
    for key in ordered:
        family, name = nodes[key]
        obj = objects.get(key, {})
        for text_field in TEXT_FIELDS_BY_FAMILY.get(family, ()):
            text = obj.get(text_field)
            if not isinstance(text, str):
                continue
            location = key + ":" + text_field
            raw = sha256_of_text(text)
            normalized = sha256_of_text(normalize_authoring_text(text))
            text_hashes[location] = {"raw_sha256": raw,
                                     "normalized_sha256": normalized}
            steps.append(_step(
                len(steps) + 1, operation=OPERATION_REPLACE,
                target_kind=_replace_target_kind(family, text_field),
                target_name=name, source_location=location,
                expected_before_kind=EXPECTED_BEFORE_CREATED_IN_THIS_PLAN,
                expected_before_sha256=None,
                planned_after_sha256=raw,
                planned_after_normalized_sha256=normalized,
                created_by_sequence=create_sequence.get(key)))
            replaced.append(location)
    return replaced


_MODIFICATION_REQUIRED = frozenset({"family", "name", "field",
                                    "expected_before_sha256", "text"})


def _check_modifications(spec: Any, criados: set[str],
                         problems: list[str]) -> list[dict]:
    """Alterações de objeto PREEXISTENTE — o vocabulário da fase R2.

    Cada entrada declara o objeto, o documento, o **hash do texto atual** e o
    texto novo. O hash anterior não é enfeite: sem ele, sobrescrever um objeto
    que este plano não criou é escrita cega, e a diferença entre alteração
    transacional e escrita cega é exatamente esse campo.

    Recusa alteração de objeto que a própria spec cria. As duas procedências
    existem para casos diferentes, e misturá-las faria o executor conferir o
    hash de um esqueleto que ele mesmo acabou de gerar — uma conferência que
    passa sempre e não protege nada.
    """
    raw = spec.get("modifications", [])
    if not isinstance(raw, list):
        problems.append("modifications: esperado lista.")
        return []

    saida: list[dict] = []
    vistos: set[tuple[str, str]] = set()
    for indice, item in enumerate(raw):
        rotulo = "modifications[%d]" % indice
        if not isinstance(item, dict):
            problems.append("%s: esperado objeto." % rotulo)
            continue

        desconhecidos = sorted(set(item) - _MODIFICATION_REQUIRED)
        if desconhecidos:
            problems.append("%s: campo(s) desconhecido(s): %s"
                            % (rotulo, ", ".join(desconhecidos)))
        faltando = sorted(_MODIFICATION_REQUIRED - set(item))
        if faltando:
            problems.append("%s: campo(s) obrigatório(s) ausente(s): %s"
                            % (rotulo, ", ".join(faltando)))
            continue

        familia = item.get("family")
        if familia not in TEXT_FIELDS_BY_FAMILY:
            problems.append("%s.family: %r fora do vocabulário: %s"
                            % (rotulo, familia,
                               ", ".join(sorted(TEXT_FIELDS_BY_FAMILY))))
            continue

        campo = item.get("field")
        if campo not in TEXT_FIELDS_BY_FAMILY[familia]:
            problems.append(
                "%s.field: %r não existe em %r; documentos: %s"
                % (rotulo, campo, familia,
                   ", ".join(TEXT_FIELDS_BY_FAMILY[familia])))
            continue

        nome = item.get("name")
        if not _is_valid_iec_name(nome):
            problems.append("%s.name: %s" % (rotulo, _explain_invalid_name(nome)))
            continue

        if nome in criados:
            problems.append(
                "%s: %r é criado por esta mesma spec. Alteração de preexistente "
                "e criação são procedências diferentes — conferir o hash de um "
                "esqueleto que o plano acabou de gerar é uma verificação que "
                "passa sempre e não protege nada." % (rotulo, nome))
            continue

        anterior = item.get("expected_before_sha256")
        if not isinstance(anterior, str) or not _SHA256_RE.match(anterior):
            problems.append(
                "%s.expected_before_sha256: esperado hex de 64 caracteres, "
                "medido por leitura read-only do projeto — não declarado de "
                "memória." % rotulo)
            continue

        texto = item.get("text")
        if not isinstance(texto, str):
            problems.append("%s.text: esperado string." % rotulo)
            continue

        chave = (nome, campo)
        if chave in vistos:
            problems.append(
                "%s: %r/%s aparece mais de uma vez — duas alterações do mesmo "
                "documento tornam indeterminado qual conteúdo fica."
                % (rotulo, nome, campo))
            continue
        vistos.add(chave)

        saida.append({"family": familia, "name": nome, "field": campo,
                      "expected_before_sha256": anterior.lower(),
                      "text": texto})
    return saida


def _emit_modification_steps(modifications: list[dict], steps: list[dict],
                             text_hashes: dict[str, dict]) -> list[str]:
    """Fase 2b: os `replace` sobre objeto PREEXISTENTE, com o hash anterior
    MEDIDO viajando no passo."""
    alterados: list[str] = []
    for item in modifications:
        location = "modify:%s:%s:%s" % (item["family"], item["name"],
                                        item["field"])
        raw = sha256_of_text(item["text"])
        normalized = sha256_of_text(normalize_authoring_text(item["text"]))
        text_hashes[location] = {"raw_sha256": raw,
                                 "normalized_sha256": normalized}
        steps.append(_step(
            len(steps) + 1, operation=OPERATION_REPLACE,
            target_kind=_replace_target_kind(item["family"], item["field"]),
            target_name=item["name"], source_location=location,
            expected_before_kind=EXPECTED_BEFORE_MEASURED,
            expected_before_sha256=item["expected_before_sha256"],
            planned_after_sha256=raw,
            planned_after_normalized_sha256=normalized))
        alterados.append(location)
    return alterados


def _derive_allowlist(steps: list[dict]) -> tuple[list[str], list[dict]]:
    """A allowlist NECESSÁRIA é DERIVADA dos passos, nunca declarada pelo autor
    da spec.

    Se o autor pudesse declarar quais operações o plano precisa, ele poderia
    declarar menos do que usa (e a sessão bateria numa guarda no meio da
    cadeia) ou mais do que usa (e a fase abriria permissão que ninguém exerce
    — exatamente o que docs/30 recusou ao deixar `create_pou` de fora). Aqui a
    allowlist é uma função dos passos: mudou o plano, mudou a allowlist.

    Devolve `(allowlist ordenada, lacunas de medição)`. Operação mutável sem
    API catalogada NÃO entra na allowlist e vira lacuna — fail-closed.
    """
    required: set[str] = set()
    gaps: list[dict] = []
    uncataloged: set[str] = set()
    unproven: set[str] = set()
    for step in steps:
        contract = EXECUTOR_CONTRACT.get(step["operation"])
        if contract is None:
            continue
        if not contract["mutating"]:
            continue
        # ESCRITA DE PROPRIEDADE: a allowlist não vem do contrato, e sim do
        # PASSO. Uma spec que configura só o intervalo exige `set:interval` e
        # mais nada — um nome único para a operação inteira autorizaria as
        # quatro propriedades de uma vez, que é a abertura ampla com outro
        # nome.
        if step["operation"] == OPERATION_CONFIGURE_TASK:
            for escrita in (step.get("task_properties") or []):
                required.add("set:" + escrita["property"])
            if not contract.get("field_proven"):
                unproven.add(step["operation"])
            continue
        if contract["cataloged"] and contract["mastertool_operation"]:
            required.add(contract["mastertool_operation"])
            # Catalogada e ainda assim não exercida: entra na allowlist (a
            # fase precisaria dela) E vira lacuna (o plano não é executável).
            # Os dois ao mesmo tempo, de propósito — a allowlist descreve o que
            # a operação exigiria; a lacuna diz que ninguém provou que exigir
            # basta.
            if not contract.get("field_proven"):
                unproven.add(step["operation"])
        else:
            uncataloged.add(step["operation"])
    for operation in sorted(uncataloged):
        gaps.append({
            "kind": GAP_UNCATALOGED_MASTERTOOL_OPERATION,
            "detail": (
                f"a operação de plano {operation!r} muta o projeto, mas a API "
                "do MasterTool que a realiza não está no registro literal de "
                "docs/27 §7 (MASTERTOOL_MUTATING_OPERATIONS). Catalogar a API "
                "por medição vem antes de executar este plano."),
        })
    for operation in sorted(unproven):
        gaps.append({
            "kind": GAP_OPERATION_NOT_FIELD_PROVEN,
            "detail": (
                f"a operação de plano {operation!r} tem API catalogada, mas "
                "nunca foi exercida contra o produto real dentro de uma cadeia "
                "que persistiu (save_as) e compilou (build). API existente não "
                "é operação provada, e executar aqui seria prometer o que "
                "ninguém mediu."),
        })
    return sorted(required), gaps


def _task_binding_gaps(steps: list[dict],
                       created_tasks: list[str]) -> list[dict]:
    """Vincular programa a task que o plano não cria, e que não é a do perfil.

    As duas formas medidas de vincular são fechadas: `UserPrg` serve à
    `MainTask` porque é a POU do perfil DELA, e a lista de POUs serve à task que
    este plano acabou de criar, cujo estado inicial é conhecido — vazia.

    Uma task que já estava no projeto não é nenhum dos dois casos. Ela pode ter
    POUs, ordem e comentários que ninguém leu, e o `add` entraria no fim de uma
    lista cujo conteúdo o plano não conhece. Isso é lacuna de MEDIÇÃO, não erro
    de spec: o passo continua no plano, e o plano sai não executável.
    """
    orfas = sorted({
        step["task_name"] for step in steps
        if step["operation"] == OPERATION_BIND_PROGRAM_TO_TASK
        and step["task_name"] not in created_tasks})
    return [{
        "kind": GAP_UNMEASURED_TASK_BINDING,
        "detail": (
            f"o plano vincula programa à task {task!r}, que ele não cria e que "
            f"não é a task do perfil ({PROFILE_TASK_NAME!r}). As duas formas "
            "medidas de vincular pressupõem uma coisa ou outra: `UserPrg` roda "
            f"pela cadeia de {PROFILE_TASK_NAME!r}, e a lista de POUs só tem "
            "estado inicial conhecido quando é este plano que cria a task. "
            "Ler e escrever a lista de uma task preexistente nunca foi medido."),
    } for task in orfas]


def _language_gaps(steps: list[dict]) -> list[dict]:
    """GUID de linguagem não medido é LACUNA, não erro: o formato está certo
    (o validador já provou), mas só o GUID de ST foi observado em runtime."""
    unmeasured = sorted({
        step["language_guid"] for step in steps
        if isinstance(step["language_guid"], str)
        and step["language_guid"].lower() not in MEASURED_LANGUAGE_GUIDS})
    return [{
        "kind": GAP_UNMEASURED_LANGUAGE_GUID,
        "detail": (
            f"o GUID de linguagem {guid!r} tem formato válido, mas nunca foi "
            "medido em runtime; o único GUID medido é o de ST "
            f"({MEASURED_LANGUAGE_GUIDS[0]}, probe 29 / docs/30)."),
    } for guid in unmeasured]


def _verification_limits(steps: list[dict], creation_order: list[str],
                         task_names: list[str],
                         program_call_pairs: list[tuple[str, str]]) -> list[dict]:
    """O que o passo `verify` NÃO consegue afirmar, dado o que a API permite
    medir hoje. Declarado no artefato, não escondido num comentário."""
    limits: list[dict] = []
    if any(isinstance(step["language_guid"], str) for step in steps):
        limits.append({
            "kind": LIMIT_LANGUAGE_NOT_READABLE,
            "detail": (
                "não há API catalogada para LER a linguagem de um objeto já "
                "existente. `language_guid` é parâmetro de entrada de "
                "create_* (Nullable<Guid>, docs/30) e NÃO pode ser "
                "reconferido depois; o passo verify não afirma nada sobre "
                "linguagem."),
        })
    if creation_order:
        limits.append({
            "kind": LIMIT_DIRECT_CHILDREN_ONLY,
            "detail": (
                "a varredura da árvore usa get_children(False) — só filhos "
                "diretos. expected_tree.persistent_additions é uma lista de UM "
                "nível, do container IEC; o plano nunca emite create_folder e "
                "nunca aninha objeto em objeto, para permanecer comparável "
                "com o que o verificador mede."),
        })
    if task_names or program_call_pairs:
        limits.append({
            "kind": LIMIT_TASK_CONTAINER_SEPARATE,
            "detail": (
                "tasks vivem na Task Configuration e Program Calls são filhas "
                "de uma task: nenhuma aparece num get_children(False) da "
                "Application. Por isso estão em listas separadas de "
                "expected_tree, e somá-las a persistent_additions faria o diff "
                "acusar ausência de objetos que aquele container nunca "
                "mostraria."),
        })
    return limits


def build_authoring_plan(spec: Any, expected_template: Any = None) -> PlanResult:
    """Constrói o plano de autoria a partir de `project_spec`.

    NUNCA levanta. Entrada degenerada (`None`, `[]`, `"x"`, `3`, `True`, dict
    malformado em qualquer nível) devolve `PlanResult` com `problems` e
    `plan=None`. `expected_template`, quando fornecido, é o template que o
    chamador exige que a spec declare.
    """
    try:
        return _build_authoring_plan(spec, expected_template)
    except Exception as exc:                                    # noqa: BLE001
        # Rede de segurança, não desculpa: qualquer caminho que chegue aqui é
        # defeito deste módulo. Ainda assim o chamador recebe um resultado
        # fechado, porque um planner que levanta no meio de um pipeline
        # esconde o problema atrás de um traceback.
        return PlanResult(
            problems=["planner falhou de forma não categorizada: "
                      f"{exc!r} — nenhum plano foi produzido."],
            plan=None)


def _build_authoring_plan(spec: Any, expected_template: Any) -> PlanResult:
    validation = validate_project_spec(spec)
    problems: list[str] = list(validation.problems)

    if not isinstance(spec, dict):
        return PlanResult(problems=problems, plan=None)

    _check_template(spec, expected_template, problems)
    library_preconditions = _check_libraries(spec, problems)
    program_call_pairs = _check_program_calls(spec, problems)

    nodes = _collect_objects(spec)
    objects = _object_by_key(spec)
    graph = _build_graph(nodes, objects)

    node_order = sorted(nodes, key=lambda key: _sort_key(*nodes[key]))
    for cycle in _find_cycles(graph, node_order):
        problems.append(
            "ciclo de dependência no grafo de criação: "
            + " -> ".join(cycle)
            + " — o caminho inteiro está acima; quebre uma das arestas antes "
              "de planejar a criação, porque nenhuma ordem topológica existe "
              "enquanto ele existir.")

    ordered = _topological_order(nodes, graph)
    if len(ordered) != len(nodes):
        # Rede secundária: só acontece se houver ciclo, e o ciclo já foi
        # reportado acima com o caminho. Nunca produzir plano parcial.
        unresolved = sorted(set(nodes) - set(ordered))
        problems.append(
            "ordenação topológica não alcançou todos os objetos; ficaram "
            "pendentes: " + ", ".join(unresolved))

    # A validação das alterações entra ANTES deste portão, e não depois.
    # Depois dele, um problema seria anexado a um plano que já saiu — e o
    # plano sairia `executable: True` carregando uma modificação malformada,
    # que é o oposto de fail-closed.
    modificacoes = _check_modifications(
        spec, {nome for _familia, nome in nodes.values()}, problems)

    if problems:
        return PlanResult(problems=problems, plan=None)

    steps: list[dict] = []
    create_sequence: dict[str, int] = {}
    text_hashes: dict[str, dict] = {}

    _emit_create_steps(ordered, nodes, objects, steps, create_sequence)
    replaced = _emit_replace_steps(ordered, nodes, objects, steps,
                                   create_sequence, text_hashes)

    # Fase 2b: alterações de objeto PREEXISTENTE (R2). Vêm DEPOIS das criações
    # e dos seus replaces, e antes das chamadas: um objeto alterado pode ser
    # alvo de uma chamada emitida em seguida, e o contrário não acontece.
    alterados = _emit_modification_steps(modificacoes, steps, text_hashes)
    replaced = replaced + alterados

    task_names = sorted(
        task["name"] for task in spec.get("tasks", [])
        if isinstance(task, dict) and isinstance(task.get("name"), str))
    # TASK QUE JA EXISTE NAO E CRIADA. `MainTask` vem no `TemplateExemplo v1.project`, e
    # todas as execucoes reais a REUSARAM (docs/38 §1: reusar reduz a
    # superficie mutavel de duas operacoes estruturais para uma).
    #
    # `existing` e opcional e o default e False de proposito: quem nao diz nada
    # esta pedindo para CRIAR, e criar task nunca foi exercido contra o produto
    # -- o plano entao sai como nao executavel, por lacuna nomeada, em vez de
    # aceitar em silencio.
    existing_tasks = sorted(
        task["name"] for task in spec.get("tasks", [])
        if isinstance(task, dict) and isinstance(task.get("name"), str)
        and task.get("existing") is True)
    for task_name in task_names:
        if task_name in existing_tasks:
            continue
        steps.append(_step(
            len(steps) + 1, operation=OPERATION_CREATE_TASK,
            target_kind=TARGET_KIND_TASK, target_name=task_name,
            source_location="tasks:" + task_name,
            task_name=task_name))

    # CONFIGURAÇÃO DA TASK, antes de qualquer vínculo.
    #
    # A ordem entre as propriedades é significativa e está fixada em
    # `TASK_PROPERTY_ORDER`: o stub condiciona `interval` a `kind_of_task` já
    # ser Cyclic (L119-129), então o tipo é escrito primeiro. Deixar a ordem
    # por conta da iteração do dicionário da spec seria deixar o produto
    # receber `interval` num momento em que ele pode recusá-lo.
    #
    # Só a task que ESTE plano cria é configurada. Numa task preexistente,
    # reescrever o tempo mudaria o comportamento de um projeto que não foi
    # gerado aqui — o mesmo motivo pelo qual o vínculo a recusa.
    for task_name in task_names:
        if task_name in existing_tasks:
            continue
        declaradas = _task_properties_of(spec, task_name)
        if not declaradas:
            continue
        steps.append(_step(
            len(steps) + 1, operation=OPERATION_CONFIGURE_TASK,
            target_kind=TARGET_KIND_TASK, target_name=task_name,
            source_location="tasks:" + task_name,
            task_name=task_name, task_properties=declaradas))

    # QUAL DAS DUAS FORMAS DE VINCULAR, decidido pela TASK e não pela spec.
    #
    #   `MainTask`          -> a chamada dentro de `UserPrg` (docs/41). O
    #                          fabricante pede assim, e são 0 avisos.
    #   task criada aqui    -> a lista de POUs da própria task. O aviso do
    #                          fabricante nomeia `MainTask`, e `UserPrg` roda
    #                          pela cadeia DELA -- chegar por ali a uma task
    #                          nova ligaria o programa ao ciclo errado.
    #
    # Uma task que a spec declara `existing` e que NÃO é a do perfil não tem
    # nenhuma das duas: o passo é emitido assim mesmo, porque o plano é a
    # evidência do que se pediu, e a lacuna abaixo o torna não executável.
    # Os dois ramos escrevem `operation=` como REFERÊNCIA a uma constante, e não
    # como variável decidida antes: o nome da operação nunca é fabricado a
    # partir de dados, e há teste de AST afirmando isso passo a passo.
    for task_name, program_name in program_call_pairs:
        if task_name == PROFILE_TASK_NAME:
            steps.append(_step(
                len(steps) + 1, operation=OPERATION_CREATE_PROGRAM_CALL,
                target_kind=TARGET_KIND_PROGRAM_CALL,
                target_name=task_name + "->" + program_name,
                source_location=("tasks:" + task_name + ":program_calls:"
                                 + program_name),
                task_name=task_name, program_name=program_name))
        else:
            steps.append(_step(
                len(steps) + 1, operation=OPERATION_BIND_PROGRAM_TO_TASK,
                target_kind=TARGET_KIND_PROGRAM_CALL,
                target_name=task_name + "->" + program_name,
                source_location=("tasks:" + task_name + ":program_calls:"
                                 + program_name),
                task_name=task_name, program_name=program_name))

    steps.append(_step(
        len(steps) + 1, operation=OPERATION_SAVE_AS,
        target_kind=TARGET_KIND_PROJECT, target_name=PROJECT_TARGET,
        source_location=PROJECT_TARGET))
    steps.append(_step(
        len(steps) + 1, operation=OPERATION_REOPEN,
        target_kind=TARGET_KIND_PROJECT, target_name=PROJECT_TARGET,
        source_location=PROJECT_TARGET))
    steps.append(_step(
        len(steps) + 1, operation=OPERATION_BUILD,
        target_kind=TARGET_KIND_PROJECT, target_name=PROJECT_TARGET,
        source_location=PROJECT_TARGET))
    steps.append(_step(
        len(steps) + 1, operation=OPERATION_VERIFY,
        target_kind=TARGET_KIND_PROJECT, target_name=PROJECT_TARGET,
        source_location=PROJECT_TARGET))

    required_allowlist, gaps = _derive_allowlist(steps)
    gaps = gaps + _language_gaps(steps)
    gaps = gaps + _task_binding_gaps(
        steps, [name for name in task_names if name not in existing_tasks])

    persistent_additions = [nodes[key][1] for key in ordered]

    expected_tree = {
        "persistent_additions": persistent_additions,
        "task_additions": task_names,
        "program_call_additions": [pair[0] + "->" + pair[1]
                                   for pair in program_call_pairs],
        "text_replacements": replaced,
        "library_preconditions": library_preconditions,
    }

    expected_diff = {family: sum(1 for key in ordered if nodes[key][0] == family)
                     for family in OBJECT_FAMILIES}
    expected_diff["tasks"] = len(task_names)
    expected_diff["program_calls"] = len(program_call_pairs)
    expected_diff["text_replacements"] = len(replaced)
    expected_diff["mutating_steps"] = sum(
        1 for step in steps
        if EXECUTOR_CONTRACT[step["operation"]]["mutating"])
    expected_diff["total_steps"] = len(steps)

    template = spec.get("template") or {}
    plan = {
        "schema_version": PLAN_SCHEMA_VERSION,
        "kind": PLAN_KIND,
        "template": {"id": template.get("id"),
                     "sha256": template.get("sha256")},
        "spec_sha256": hashlib.sha256(
            canonical_json(spec).encode("utf-8")).hexdigest(),
        "creation_order": list(ordered),
        "steps": steps,
        "expected_tree": expected_tree,
        "expected_diff": expected_diff,
        "text_hashes": text_hashes,
        "required_allowlist": required_allowlist,
        "measurement_gaps": gaps,
        # Limites de VERIFICAÇÃO, não de execução: não afetam `executable`.
        "verification_limits": _verification_limits(
            steps, ordered, task_names, program_call_pairs),
        # Fail-closed: só é executável um plano sem NENHUMA lacuna de medição.
        # Um plano com lacuna descreve corretamente o que fazer e admite que
        # parte disso ainda não foi medida — executá-lo assim mesmo seria
        # inventar MasterTool no meio de uma cadeia de mutações.
        "executable": not gaps,
    }
    plan["plan_sha256"] = hashlib.sha256(
        canonical_json(plan).encode("utf-8")).hexdigest()
    return PlanResult(problems=[], plan=plan)

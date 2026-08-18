"""Validação offline e determinística de `project_spec` (ver
`project_spec.schema.json` no mesmo diretório).

Este módulo roda no lado HOST (CPython 3), fora do MasterTool, e existe para
ser o gate ANTES de qualquer sessão de escrita controlada: `project_spec` é o
modelo declarativo do estado-alvo (quais DUTs/GVLs/FUNCTIONs/FUNCTION_BLOCKs/
PROGRAMs/tasks/libraries devem existir ao final da sessão), e este validador
prova, sem abrir o MasterTool, que a spec é coerente antes de qualquer
`create_*`/`replace`/`save_as` ser sequer planejado.

Fail-closed deliberado, no mesmo espírito de
`automation/config_models.py`: campo desconhecido em qualquer nível reprova;
nome inválido reprova; referência para objeto inexistente reprova; ciclo
entre FBs/FUNCTIONs reprova. Nenhuma dessas checagens usa a biblioteca
`jsonschema` — são reimplementadas aqui, explicitamente, porque o contrato
desta frente pede validação sem nova dependência externa.

Fatos medidos que este módulo respeita (não reinventa):
  - a linguagem ST é identificada pelo GUID `cc393387-a21c-4f68-a3e3-
    84c36951965d`, nunca pela string "ST" — o parâmetro real da API é
    `Nullable<Guid>`, e aceitar texto seria inventar uma API que não existe
    (docs/30-plano-w1-2-criacao-program-st.md, seção "O GUID não viaja como
    texto");
  - o `type_guid` de POU (`6f9dac99-8de1-4efc-8465-68ac443b7d08`) identifica
    "é um POU", não distingue PROGRAM de FUNCTION_BLOCK/FUNCTION — por isso
    este validador NUNCA usa type_guid para separar essas famílias; a família
    (`programs` vs `function_blocks` vs `functions`) é o único discriminador,
    porque é o único que a spec declara e o único que foi medido.

Este módulo `nunca levanta` em entrada malformada (`None`, lista, string,
dict com formas erradas) — sempre devolve um `ValidationResult` com
`problems` preenchido. Quem decide interromper uma sessão a partir disso é o
chamador.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field
from typing import Any

SCHEMA_VERSION = 1

# GUID da linguagem ST, medido em runtime pelo probe 29 (docs/30). A string
# "ST" nunca é aceita no lugar deste GUID: o parâmetro real da API é
# `Nullable<Guid>`, e aceitar texto inventaria uma API que não existe.
ST_LANGUAGE_GUID = "cc393387-a21c-4f68-a3e3-84c36951965d"

_GUID_RE = re.compile(
    r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-"
    r"[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$")

# Nome IEC válido: começa com letra ou '_', seguido de letras/dígitos/'_'.
# Comprimento máximo é DECISÃO deste slice (não medida) — 64 é generoso o
# bastante para qualquer identificador real e curto o bastante para pegar
# geração acidental de texto absurdamente longo.
_IEC_NAME_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
MAX_IEC_NAME_LENGTH = 64

# Lista FECHADA de palavras reservadas IEC 61131-3 usada por este validador.
# É uma DECISÃO deste slice, não uma medição contra o MasterTool: cobre as
# palavras-chave estruturais e de tipo mais comuns da norma. Uma lista maior
# (POUs, ações, todos os operadores) pode ser adicionada depois sem quebrar
# specs já válidas — só torna a validação mais estrita.
IEC_RESERVED_WORDS = frozenset({
    "PROGRAM", "END_PROGRAM", "FUNCTION", "END_FUNCTION",
    "FUNCTION_BLOCK", "END_FUNCTION_BLOCK", "ACTION", "END_ACTION",
    "METHOD", "END_METHOD", "PROPERTY", "END_PROPERTY",
    "INTERFACE", "END_INTERFACE", "TYPE", "END_TYPE",
    "STRUCT", "END_STRUCT", "VAR", "END_VAR",
    "VAR_INPUT", "VAR_OUTPUT", "VAR_IN_OUT", "VAR_GLOBAL",
    "VAR_TEMP", "VAR_STAT", "VAR_EXTERNAL", "VAR_CONFIG", "VAR_ACCESS",
    "IF", "THEN", "ELSE", "ELSIF", "END_IF",
    "CASE", "OF", "END_CASE",
    "FOR", "TO", "BY", "DO", "END_FOR",
    "WHILE", "END_WHILE", "REPEAT", "UNTIL", "END_REPEAT",
    "EXIT", "CONTINUE", "RETURN",
    "TASK", "END_TASK", "CONFIGURATION", "END_CONFIGURATION",
    "RESOURCE", "END_RESOURCE", "PROGRAM_NAME",
    "BOOL", "BYTE", "WORD", "DWORD", "LWORD",
    "SINT", "INT", "DINT", "LINT",
    "USINT", "UINT", "UDINT", "ULINT",
    "REAL", "LREAL", "TIME", "DATE", "DT", "TOD", "STRING", "WSTRING",
    "TRUE", "FALSE", "NOT", "AND", "OR", "XOR", "MOD",
})

# Famílias que compartilham o mesmo container/namespace (a Application do
# MasterTool) — dois objetos com o mesmo nome entre elas são conflito real,
# porque a árvore não permite dois filhos-irmãos com o mesmo nome. `tasks` e
# `libraries` vivem em containers próprios (Task Configuration / Library
# Manager) e por isso só são checados por duplicata DENTRO da própria
# família, nunca contra as demais.
_APPLICATION_NAMESPACE_FAMILIES = (
    "duts", "gvls", "functions", "function_blocks", "programs")

_ALL_FAMILIES = _APPLICATION_NAMESPACE_FAMILIES + ("tasks", "libraries")

# `modifications` NÃO é uma família de objeto: é a lista de alterações sobre
# objeto PREEXISTENTE (fase R2). Ela não cria nada, não entra em
# `creation_order` e não conta em `expected_diff` — a árvore não muda quando só
# o texto muda (medido em W1.3A, docs/33). Quem valida a forma dela é o
# planner, que é onde o hash anterior medido tem significado.
_TOP_LEVEL_KNOWN_KEYS = frozenset(
    {"schema_version", "template", "modifications"} | set(_ALL_FAMILIES))

_REQUIRED_BY_FAMILY = {
    "duts": {"name", "kind", "declaration"},
    "gvls": {"name", "declaration"},
    "functions": {"name", "language", "declaration", "implementation", "return_type"},
    "function_blocks": {"name", "language", "declaration", "implementation"},
    "programs": {"name", "language", "declaration", "implementation"},
    "tasks": {"name", "program_calls"},
    "libraries": {"name"},
}

_OPTIONAL_BY_FAMILY = {
    "duts": {"language", "uses"},
    "gvls": {"language", "uses"},
    "functions": {"uses"},
    # `methods`: R3.1B (docs/87). SÓ em `function_blocks`. A matriz do docs/86
    # mediu `create_method` alcançável também em PROGRAM e FUNCTION, e o
    # contrato recusa ler isso como autorização geral — `PRESENT ≠ necessário ≠
    # qualificado`. Deixar o campo fora de `functions` e `programs` faz a
    # rejeição ser de SCHEMA, e não de convenção.
    "function_blocks": {"uses", "methods"},
    "programs": {"uses"},
    # `existing`: a task JÁ EXISTE no template e deve ser REUSADA, nunca
    # criada. A `MainTask` do template é assim, e foi o que todas as execuções
    # reais fizeram (docs/38 §1, docs/39, docs/41). Opcional e com default
    # `False` de propósito — quem não diz nada está pedindo para CRIAR.
    #
    # Os QUATRO parâmetros de tempo entram aqui porque, sem eles, a spec
    # descreve a estrutura certa e o tempo errado. `docs/48` §4 mediu com que
    # valores uma task criada nasce: `t#20ms` e prioridade `1` — mais rápida e
    # de prioridade mais alta que a própria `MainTask` (100 ms, prioridade 13).
    # Nada disso vinha da spec, e a fábrica não sabia mudar.
    #
    # Todos OPCIONAIS: quem não declara fica com o default do produto, que é o
    # comportamento que `docs/48` documentou. Declarar parcialmente é legítimo —
    # só o que estiver escrito é escrito.
    "tasks": {"existing", "kind_of_task", "interval", "interval_unit",
              "priority"},
    "libraries": set(),
}

# Famílias cujos objetos podem ter texto declarado (para efeito de
# `text_hashes`), e quais campos de texto cada uma carrega.
_TEXT_FIELDS_BY_FAMILY = {
    "duts": ("declaration",),
    "gvls": ("declaration",),
    "functions": ("declaration", "implementation"),
    "function_blocks": ("declaration", "implementation"),
    "programs": ("declaration", "implementation"),
}

# Ordem de criação exigida pelo contrato (Frente E, seção "Fatos medidos"):
# DUTs -> GVLs -> FUNCTIONs -> FBs -> PROGRAMs -> tasks -> program calls.
_CREATION_FAMILY_ORDER = (
    "duts", "gvls", "functions", "function_blocks", "programs", "tasks")

# Famílias entre as quais é válido declarar `uses` (dependências permitidas).
# Uma família só pode depender de si mesma e das que vêm ANTES dela na ordem
# de criação — depender de algo criado depois seria uma referência para um
# objeto que ainda não existe no momento da criação.
_ALLOWED_USES_TARGETS = {
    "duts": {"duts"},
    "gvls": {"duts", "gvls"},
    "functions": {"duts", "gvls", "functions"},
    "function_blocks": {"duts", "gvls", "functions", "function_blocks"},
    "programs": {"duts", "gvls", "functions", "function_blocks"},
}

# Famílias entre as quais ciclo é verificado (contrato: "ciclos inválidos
# entre FBs/FUNCTIONs"). DUTs/GVLs/PROGRAMs ficam fora deste grafo: DUTs só
# apontam para trás na mesma ordem de criação (aninhamento de STRUCT), GVLs
# não chamam nada, e PROGRAMs não são chamáveis por outro objeto nesta spec.
_CYCLE_FAMILIES = ("functions", "function_blocks")


class ValidationError(ValueError):
    """Reservado para uso futuro por chamadores que queiram transformar
    `problems` em exceção. `validate_project_spec` nunca a levanta."""


@dataclass
class ValidationResult:
    """Resultado de `validate_project_spec`.

    `problems` vazio é a única condição de sucesso. As demais listas/dicts
    são sempre devolvidas com o melhor esforço possível mesmo quando há
    problemas — mas `creation_order`/`expected_diff`/`text_hashes` só devem
    ser usados por um chamador quando `problems == []`."""

    problems: list[str] = field(default_factory=list)
    creation_order: list[str] = field(default_factory=list)
    expected_diff: dict[str, int] = field(default_factory=dict)
    text_hashes: dict[str, str] = field(default_factory=dict)

    @property
    def ok(self) -> bool:
        return not self.problems


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _is_valid_iec_name(name: str) -> bool:
    if not isinstance(name, str):
        return False
    if not (1 <= len(name) <= MAX_IEC_NAME_LENGTH):
        return False
    if not _IEC_NAME_RE.match(name):
        return False
    return name.upper() not in IEC_RESERVED_WORDS


def _explain_invalid_name(name: Any) -> str:
    if not isinstance(name, str) or not name:
        return "deve ser uma string não vazia"
    if len(name) > MAX_IEC_NAME_LENGTH:
        return f"excede o máximo de {MAX_IEC_NAME_LENGTH} caracteres"
    if not _IEC_NAME_RE.match(name):
        return "deve começar com letra ou '_' e conter só letras/dígitos/'_'"
    if name.upper() in IEC_RESERVED_WORDS:
        return f"'{name}' é palavra reservada IEC, escolha outro nome"
    return "nome IEC inválido"


def _validate_language(family: str, name: str, language: Any, problems: list[str]) -> None:
    """Valida o campo `language`. A string "ST" é recusada explicitamente:
    o parâmetro real da API é `Nullable<Guid>`, e texto no lugar do GUID
    seria inventar uma API que não existe."""
    if language is None:
        return
    if isinstance(language, str):
        problems.append(
            f"{family}.{name}.language: recebido a string {language!r} — a "
            "linguagem é sempre um GUID (ex.: language={'guid': "
            f"'{ST_LANGUAGE_GUID}'}}), nunca a string \"ST\"; o parâmetro "
            "real da API é Nullable<Guid> e texto aqui inventaria uma API "
            "que não existe.")
        return
    if not isinstance(language, dict):
        problems.append(
            f"{family}.{name}.language: deve ser um objeto {{'guid': "
            f"'<GUID>'}}, recebido {type(language).__name__}.")
        return
    unknown = set(language.keys()) - {"guid"}
    if unknown:
        problems.append(
            f"{family}.{name}.language: chave(s) desconhecida(s): "
            + ", ".join(sorted(unknown)) + " — remova-as, só 'guid' é aceito.")
    guid = language.get("guid")
    if not isinstance(guid, str) or not _GUID_RE.match(guid):
        problems.append(
            f"{family}.{name}.language.guid: {guid!r} não é um GUID "
            "válido no formato 8-4-4-4-12 (ex.: "
            f"'{ST_LANGUAGE_GUID}'); corrija para o GUID medido em runtime.")


_METHOD_REQUIRED = frozenset({"name", "declaration", "implementation"})
_METHOD_OPTIONAL = frozenset({"return_type"})


def _validate_methods(family: str, owner: str, methods: Any,
                      problems: list[str]) -> None:
    """Valida a lista de `METHOD` de um `FUNCTION_BLOCK` (R3.1B, docs/87).

    Duas coisas que este validador NÃO faz, e ambas por decisão medida:

    * não aceita `language` no membro. O parâmetro da API é `Nullable<Guid>`
      com default `null`, e não existe rota para LER a linguagem do owner
      (`docs/api` §5). O owner já a declara; duplicar aqui criaria duas fontes
      de verdade para um valor que nem se confere contra o produto.
    * não exige `return_type`. Ausente ou `null` é **método sem retorno**, que
      é a representação nativa da API: `create_method` tem default `null`,
      enquanto `create_property` tem default `int` — o produto distingue as duas
      famílias. Converter ausência em `BOOL` ou `VOID` seria inventar IEC.
    """
    if family != "function_blocks":
        problems.append(
            f"{family}.{owner}.methods: `methods` só existe em "
            "'function_blocks'. O escopo qualificado do R3.1B é "
            "FUNCTION_BLOCK → METHOD (docs/87 §2); `create_method` foi medido "
            "alcançável também em PROGRAM e FUNCTION, e isso NÃO é autorização.")
        return

    if not isinstance(methods, list):
        problems.append(
            f"function_blocks.{owner}.methods: deve ser lista, recebido "
            f"{type(methods).__name__}.")
        return

    vistos: dict[str, int] = {}
    for i, metodo in enumerate(methods):
        local = f"function_blocks.{owner}.methods[{i}]"
        if not isinstance(metodo, dict):
            problems.append(
                f"{local}: deve ser um objeto (dict), recebido "
                f"{type(metodo).__name__}.")
            continue

        desconhecidos = set(metodo.keys()) - (_METHOD_REQUIRED | _METHOD_OPTIONAL)
        if desconhecidos:
            problems.append(
                f"{local}: campo(s) desconhecido(s), fail-closed: "
                + ", ".join(sorted(desconhecidos))
                + " — campos aceitos: "
                + ", ".join(sorted(_METHOD_REQUIRED | _METHOD_OPTIONAL)))

        faltando = _METHOD_REQUIRED - set(metodo.keys())
        if faltando:
            problems.append(
                f"{local}: campo(s) obrigatório(s) ausente(s): "
                + ", ".join(sorted(faltando)))

        nome = metodo.get("name")
        if not _is_valid_iec_name(nome):
            problems.append(f"{local}.name: {_explain_invalid_name(nome)}")
        else:
            # Duplicata é erro DENTRO do owner: dois `METHOD` de mesmo nome no
            # mesmo FB não são dois objetos, são um pedido ambíguo — e o
            # executor não teria como decidir qual reencontrar depois.
            if nome in vistos:
                problems.append(
                    f"function_blocks.{owner}.methods: nome '{nome}' repetido "
                    f"(índices {vistos[nome]} e {i}). A identidade do membro é "
                    "owner + METHOD + nome (docs/87 §6).")
            else:
                vistos[nome] = i

        for campo in ("declaration", "implementation"):
            if campo in metodo and not isinstance(metodo[campo], str):
                problems.append(
                    f"{local}.{campo}: deve ser string, recebido "
                    f"{type(metodo[campo]).__name__}.")

        if "return_type" in metodo:
            rt = metodo["return_type"]
            if rt is not None and (not isinstance(rt, str) or not rt):
                problems.append(
                    f"{local}.return_type: deve ser string não vazia ou null. "
                    "Ausente ou null significa MÉTODO SEM RETORNO — nunca "
                    "converter em 'BOOL' nem 'VOID'.")


def _validate_object(family: str, index: int, obj: Any, problems: list[str]) -> str | None:
    """Valida um objeto de uma família. Devolve o nome (se extraível) para
    que o chamador ainda possa usá-lo em checagens de duplicata/referência
    mesmo quando outras partes do objeto reprovaram."""
    location = f"{family}[{index}]"
    if not isinstance(obj, dict):
        problems.append(
            f"{location}: deve ser um objeto (dict), recebido "
            f"{type(obj).__name__} — corrija a entrada inteira.")
        return None

    required = _REQUIRED_BY_FAMILY[family]
    optional = _OPTIONAL_BY_FAMILY[family]
    allowed = required | optional

    unknown = set(obj.keys()) - allowed
    if unknown:
        problems.append(
            f"{location}: campo(s) desconhecido(s), fail-closed: "
            + ", ".join(sorted(unknown))
            + f" — campos aceitos em '{family}': " + ", ".join(sorted(allowed)))

    missing = required - set(obj.keys())
    if missing:
        problems.append(
            f"{location}: campo(s) obrigatório(s) ausente(s): "
            + ", ".join(sorted(missing)))

    name = obj.get("name")
    if not _is_valid_iec_name(name):
        problems.append(f"{location}.name: {_explain_invalid_name(name)}")
        name_out = name if isinstance(name, str) and name else None
    else:
        name_out = name

    label = name_out if name_out is not None else f"[{index}]"

    if family == "duts":
        kind = obj.get("kind")
        if kind not in ("STRUCT", "ENUM"):
            problems.append(
                f"{family}.{label}.kind: {kind!r} inválido, use 'STRUCT' ou 'ENUM'.")

    if "language" in obj or family in ("functions", "function_blocks", "programs"):
        _validate_language(family, label, obj.get("language"), problems)

    for text_field in _TEXT_FIELDS_BY_FAMILY.get(family, ()):
        if text_field in obj and not isinstance(obj[text_field], str):
            problems.append(
                f"{family}.{label}.{text_field}: deve ser string, recebido "
                f"{type(obj[text_field]).__name__}.")

    if family == "functions":
        return_type = obj.get("return_type")
        if not isinstance(return_type, str) or not return_type:
            problems.append(
                f"{family}.{label}.return_type: deve ser string não vazia "
                "(ex.: 'BOOL').")

    if "methods" in obj:
        _validate_methods(family, label, obj["methods"], problems)

    if "uses" in obj:
        uses = obj["uses"]
        if not isinstance(uses, list) or not all(isinstance(u, str) for u in uses):
            problems.append(
                f"{family}.{label}.uses: deve ser lista de strings (nomes "
                "referenciados).")

    if family == "tasks":
        calls = obj.get("program_calls")
        if not isinstance(calls, list) or not all(isinstance(c, str) for c in calls):
            problems.append(
                f"{family}.{label}.program_calls: deve ser lista de strings "
                "(nomes de PROGRAM).")

    return name_out


def _collect_family(spec: dict, family: str, problems: list[str]) -> list[tuple[int, dict, str | None]]:
    raw = spec.get(family, [])
    if raw == []:
        return []
    if not isinstance(raw, list):
        problems.append(
            f"{family}: deve ser uma lista, recebido {type(raw).__name__}.")
        return []
    collected: list[tuple[int, dict, str | None]] = []
    for index, obj in enumerate(raw):
        name = _validate_object(family, index, obj, problems)
        collected.append((index, obj if isinstance(obj, dict) else {}, name))
    return collected


def _check_duplicates(
        by_family: dict[str, list[tuple[int, dict, str | None]]],
        problems: list[str]) -> None:
    # Duplicatas DENTRO de cada família.
    for family, items in by_family.items():
        seen: dict[str, int] = {}
        for _, _, name in items:
            if name is None:
                continue
            if name in seen:
                problems.append(
                    f"{family}: nome '{name}' duplicado dentro da mesma "
                    "família — cada objeto precisa de nome único.")
            else:
                seen[name] = 1

    # Duplicatas ENTRE famílias que compartilham o namespace da Application.
    owner_of: dict[str, str] = {}
    for family in _APPLICATION_NAMESPACE_FAMILIES:
        for _, _, name in by_family.get(family, []):
            if name is None:
                continue
            if name in owner_of and owner_of[name] != family:
                problems.append(
                    f"nome '{name}' conflita entre '{owner_of[name]}' e "
                    f"'{family}' — dois objetos com o mesmo nome no mesmo "
                    "container (Application) não podem coexistir.")
            else:
                owner_of.setdefault(name, family)


def _check_references(
        by_family: dict[str, list[tuple[int, dict, str | None]]],
        problems: list[str]) -> None:
    all_names_by_family = {
        family: {name for _, _, name in items if name is not None}
        for family, items in by_family.items()
    }

    for family in ("duts", "gvls", "functions", "function_blocks", "programs"):
        allowed_targets = _ALLOWED_USES_TARGETS.get(family, set())
        for _, obj, name in by_family.get(family, []):
            if name is None:
                continue
            uses = obj.get("uses")
            if not isinstance(uses, list):
                continue
            for used_name in uses:
                if not isinstance(used_name, str):
                    continue
                found_in = [
                    target for target in allowed_targets
                    if used_name in all_names_by_family.get(target, set())
                ]
                if found_in:
                    continue
                # Existe em alguma família fora do permitido, ou não existe.
                exists_anywhere = any(
                    used_name in all_names_by_family.get(other, set())
                    for other in _APPLICATION_NAMESPACE_FAMILIES
                )
                if exists_anywhere:
                    problems.append(
                        f"{family}.{name}.uses: '{used_name}' existe na spec, "
                        f"mas '{family}' só pode referenciar "
                        + ", ".join(sorted(allowed_targets)) + " (ordem de "
                        "criação: uma dependência não pode apontar para algo "
                        "criado depois dela).")
                else:
                    problems.append(
                        f"{family}.{name}.uses: '{used_name}' não existe na "
                        "spec — adicione o objeto referenciado (dut/gvl/"
                        "function/function_block) ou remova a referência.")

    program_names = all_names_by_family.get("programs", set())
    for _, obj, name in by_family.get("tasks", []):
        if name is None:
            continue
        calls = obj.get("program_calls")
        if not isinstance(calls, list):
            continue
        for called in calls:
            if not isinstance(called, str):
                continue
            if called not in program_names:
                problems.append(
                    f"tasks.{name}.program_calls: '{called}' não existe em "
                    "'programs' — toda program call precisa referenciar um "
                    "PROGRAM declarado na spec.")

    _validate_task_timing(by_family, problems)


# Membros do enum `KindOfTask`, LITERAIS, do stub que o produto instala
# (`ScriptTaskConfigObject.pyi` L5-11). A run-031 (docs/45) mediu que o enum é
# injetado no escopo do script.
_KINDS_OF_TASK = ("Cyclic", "Freewheeling", "Event", "ExternalEvent", "Status",
                  "ParentSynchron")

# Os únicos que a fábrica sabe configurar por completo. `Event` e `Status`
# exigem `event`, e `ExternalEvent` exige `external_event` — campos que o
# registro de escrita de propriedade não cobre, e uma task desses tipos sem o
# gatilho seria estrutura sem semântica.
_KINDS_OF_TASK_SUPPORTED = ("Cyclic", "Freewheeling")

# `interval` é `str` no stub, e o produto aceita mais de uma grafia: a
# `MainTask` do template lê `'100'` e a task recém-criada lê `'t#20ms'`
# (docs/48 §4). As duas formas são aceitas aqui porque as duas foram OBSERVADAS
# no produto; nenhuma terceira é inventada.
_INTERVAL_IEC = re.compile(r"^[tT]#[0-9]+(ms|us|s)$")
_INTERVAL_NUMERO = re.compile(r"^[0-9]+$")
_INTERVAL_UNITS = ("ms", "us", "s")


def _validate_task_timing(by_family, problems) -> None:
    """Os quatro parâmetros de tempo da task.

    Validação CONSERVADORA: recusa o que não foi observado no produto, em vez
    de repassar e deixar o MasterTool decidir em silêncio. Uma spec que peça
    `priority: -1` deve morrer aqui, e não virar uma task cuja prioridade
    ninguém sabe qual é.
    """
    for _, obj, name in by_family.get("tasks", []):
        if name is None:
            continue
        rotulo = f"tasks.{name}"

        kind = obj.get("kind_of_task")
        if kind is not None:
            if not isinstance(kind, str) or kind not in _KINDS_OF_TASK:
                problems.append(
                    f"{rotulo}.kind_of_task: {kind!r} não é membro de "
                    "KindOfTask — os membros são "
                    + ", ".join(_KINDS_OF_TASK) + ".")
            elif kind not in _KINDS_OF_TASK_SUPPORTED:
                problems.append(
                    f"{rotulo}.kind_of_task: {kind!r} exige um gatilho "
                    "(`event` ou `external_event`) que esta spec não sabe "
                    "escrever — os tipos suportados são "
                    + ", ".join(_KINDS_OF_TASK_SUPPORTED) + ".")

        intervalo = obj.get("interval")
        if intervalo is not None:
            if not isinstance(intervalo, str) or not (
                    _INTERVAL_IEC.match(intervalo)
                    or _INTERVAL_NUMERO.match(intervalo)):
                problems.append(
                    f"{rotulo}.interval: {intervalo!r} não está em nenhuma das "
                    "duas grafias observadas no produto — 't#20ms' (literal de "
                    "tempo IEC) ou '100' (número puro, com a unidade em "
                    "`interval_unit`).")
            elif kind is not None and kind != "Cyclic":
                # O próprio stub condiciona: `interval` exige `kind_of_task`
                # Cyclic ou ExternalEvent, e ExternalEvent já foi recusado
                # acima por falta de gatilho.
                problems.append(
                    f"{rotulo}.interval: só se aplica a `kind_of_task` "
                    f"'Cyclic', e esta task declara {kind!r} (o próprio stub "
                    "condiciona a propriedade, L119-129).")

        unidade = obj.get("interval_unit")
        if unidade is not None and (not isinstance(unidade, str)
                                    or unidade not in _INTERVAL_UNITS):
            problems.append(
                f"{rotulo}.interval_unit: {unidade!r} não é uma das unidades "
                "observadas — " + ", ".join(_INTERVAL_UNITS) + ".")

        prioridade = obj.get("priority")
        if prioridade is not None:
            # `bool` é subclasse de `int` em Python, e `True` viraria
            # prioridade 1 sem que ninguém tivesse escrito 1.
            if isinstance(prioridade, bool) or not isinstance(prioridade, int):
                problems.append(
                    f"{rotulo}.priority: {prioridade!r} deve ser inteiro. O "
                    "stub declara a propriedade como `str`, e a conversão é do "
                    "executor — a spec fala em número para que 0 e '0' não "
                    "sejam duas coisas.")
            elif prioridade < 0 or prioridade > 31:
                problems.append(
                    f"{rotulo}.priority: {prioridade} fora de 0..31. A faixa "
                    "NÃO foi medida contra o produto; ela é conservadora e "
                    "vem da convenção do CODESYS, e existe para que um valor "
                    "absurdo morra aqui em vez de virar uma task cuja "
                    "prioridade ninguém sabe qual é.")


def _find_cycles(
        by_family: dict[str, list[tuple[int, dict, str | None]]]) -> list[list[str]]:
    """Ciclos entre FUNCTIONs/FUNCTION_BLOCKs (contrato: 'ciclos inválidos
    entre FBs/FUNCTIONs'). O grafo combina as duas famílias porque uma
    FUNCTION pode declarar `uses` para um FUNCTION_BLOCK e vice-versa; o
    ciclo é inválido nos dois sentidos."""
    graph: dict[str, list[str]] = {}
    for family in _CYCLE_FAMILIES:
        for _, obj, name in by_family.get(family, []):
            if name is None:
                continue
            uses = obj.get("uses")
            targets = [u for u in uses if isinstance(u, str)] if isinstance(uses, list) else []
            graph[name] = sorted(targets)

    node_set = set(graph.keys())
    WHITE, GRAY, BLACK = 0, 1, 2
    color = {node: WHITE for node in node_set}
    cycles: list[list[str]] = []

    def dfs(node: str, path: list[str]) -> None:
        color[node] = GRAY
        path.append(node)
        for neighbor in graph.get(node, []):
            if neighbor not in node_set:
                continue  # referência para fora do grafo de ciclo (checada em outro lugar)
            if color[neighbor] == GRAY:
                start = path.index(neighbor)
                cycles.append(path[start:] + [neighbor])
            elif color[neighbor] == WHITE:
                dfs(neighbor, path)
        path.pop()
        color[node] = BLACK

    for node in sorted(node_set):
        if color[node] == WHITE:
            dfs(node, [])

    return cycles


def _topological_order_within_family(
        family: str,
        items: list[tuple[int, dict, str | None]]) -> tuple[list[str], bool]:
    """Ordena os nomes de uma família por dependência interna declarada em
    `uses` (restrita à própria família), com desempate alfabético para
    determinismo. Devolve (ordem, houve_ciclo). Em caso de ciclo, cai para
    ordem alfabética simples — o problema já foi reportado por
    `_find_cycles`/`_check_references`, e a ordem aqui só precisa continuar
    determinística, não a única "correta"."""
    names = sorted(name for _, _, name in items if name is not None)
    graph: dict[str, list[str]] = {}
    for _, obj, name in items:
        if name is None:
            continue
        uses = obj.get("uses")
        targets = [u for u in uses if isinstance(u, str) and u in names] \
            if isinstance(uses, list) else []
        graph[name] = sorted(targets)

    color: dict[str, int] = {name: 0 for name in names}
    order: list[str] = []
    had_cycle = False

    def dfs(node: str) -> None:
        nonlocal had_cycle
        color[node] = 1
        for dep in graph.get(node, []):
            if color[dep] == 1:
                had_cycle = True
                continue
            if color[dep] == 0:
                dfs(dep)
        color[node] = 2
        order.append(node)

    for name in names:
        if color[name] == 0:
            dfs(name)

    if had_cycle:
        return names, True
    return order, False


def validate_project_spec(spec: Any) -> ValidationResult:
    """Valida `project_spec` offline. NUNCA levanta exceção — entrada
    degenerada (`None`, lista, string, dict malformado em qualquer nível)
    sempre produz um `ValidationResult` com `problems` preenchido."""
    problems: list[str] = []

    if not isinstance(spec, dict):
        problems.append(
            "project_spec deve ser um objeto (dict) no nível raiz, recebido "
            f"{type(spec).__name__}.")
        return ValidationResult(problems=problems)

    unknown_top = set(spec.keys()) - _TOP_LEVEL_KNOWN_KEYS
    if unknown_top:
        problems.append(
            "project_spec contém chave(s) desconhecida(s) no nível raiz, "
            "fail-closed: " + ", ".join(sorted(unknown_top)))

    schema_version = spec.get("schema_version")
    if schema_version != SCHEMA_VERSION:
        problems.append(
            f"schema_version deve ser {SCHEMA_VERSION}, recebido "
            f"{schema_version!r}.")

    template = spec.get("template")
    if not isinstance(template, dict):
        problems.append(
            "template: deve ser um objeto {'id': ..., 'sha256': ...}, "
            f"recebido {type(template).__name__ if template is not None else 'ausente'}.")
    else:
        unknown_template = set(template.keys()) - {"id", "sha256"}
        if unknown_template:
            problems.append(
                "template: chave(s) desconhecida(s): "
                + ", ".join(sorted(unknown_template)))
        template_id = template.get("id")
        if not isinstance(template_id, str) or not template_id:
            problems.append("template.id: deve ser string não vazia.")
        sha256 = template.get("sha256")
        if not isinstance(sha256, str) or not re.match(r"^[0-9a-fA-F]{64}$", sha256):
            problems.append(
                "template.sha256: deve ser um SHA-256 hex de 64 caracteres.")

    by_family: dict[str, list[tuple[int, dict, str | None]]] = {}
    for family in _ALL_FAMILIES:
        by_family[family] = _collect_family(spec, family, problems)

    _check_duplicates(by_family, problems)
    _check_references(by_family, problems)

    cycles = _find_cycles(by_family)
    for cycle in cycles:
        problems.append(
            "ciclo inválido entre FUNCTIONs/FUNCTION_BLOCKs: "
            + " -> ".join(cycle)
            + " — quebre a dependência circular antes de planejar a criação.")

    # A partir daqui, se já há problemas estruturais graves o suficiente para
    # tornar creation_order/expected_diff/text_hashes enganosos, ainda assim
    # devolvemos o melhor esforço determinístico: o contrato pede que
    # `problems` seja a fonte da verdade sobre "pode prosseguir?", não a
    # ausência das demais chaves.
    creation_order: list[str] = []
    for family in _CREATION_FAMILY_ORDER:
        items = by_family.get(family, [])
        if family == "tasks":
            names = sorted(name for _, _, name in items if name is not None)
            for name in names:
                creation_order.append(f"tasks:{name}")
            continue
        ordered_names, _ = _topological_order_within_family(family, items)
        for name in ordered_names:
            creation_order.append(f"{family}:{name}")

    # Passo final: program calls, depois de todas as tasks existirem.
    program_call_pairs: list[tuple[str, str]] = []
    for _, obj, task_name in by_family.get("tasks", []):
        if task_name is None:
            continue
        calls = obj.get("program_calls")
        if not isinstance(calls, list):
            continue
        for called in calls:
            if isinstance(called, str):
                program_call_pairs.append((task_name, called))
    # Ordem DECLARADA, pelo mesmo motivo que `planner._check_program_calls`:
    # a ordem das chamadas dentro de uma task é a ordem de execução no ciclo
    # IEC. `creation_order` é o que a verificação compara contra o projeto
    # gerado; alfabetizá-lo aqui faria a verificação aprovar uma ordem que a
    # spec não pediu, e faria o validador discordar do planner em silêncio.
    for task_name, program_name in program_call_pairs:
        creation_order.append(f"program_call:{task_name}->{program_name}")

    expected_diff: dict[str, int] = {}
    for family in _ALL_FAMILIES:
        expected_diff[family] = len(
            [1 for _, _, name in by_family.get(family, []) if name is not None])
    expected_diff["program_calls"] = len(program_call_pairs)

    text_hashes: dict[str, str] = {}
    for family, text_fields in _TEXT_FIELDS_BY_FAMILY.items():
        for _, obj, name in by_family.get(family, []):
            if name is None:
                continue
            for text_field in text_fields:
                value = obj.get(text_field)
                if isinstance(value, str):
                    text_hashes[f"{family}:{name}:{text_field}"] = _sha256(value)

    return ValidationResult(
        problems=problems,
        creation_order=creation_order,
        expected_diff=expected_diff,
        text_hashes=text_hashes,
    )

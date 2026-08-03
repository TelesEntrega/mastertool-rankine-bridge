"""Carga e validação offline e determinística de `template_registry` (ver
`template_registry.schema.json` no mesmo diretório).

Este módulo roda no lado HOST (CPython 3), fora do MasterTool, e não abre
nenhum `.project` real — ele descreve, declarativamente, os templates
congelados que uma sessão de escrita controlada (Frente E) pode usar como
base, e valida essa descrição antes de qualquer `node_path` ser usado para
localizar um container na árvore.

Fail-closed deliberado, no mesmo espírito de
`mastertool_bridge.spec.validator` e de `automation/config_models.py`: campo
desconhecido em qualquer nível reprova; `allow_download: true` numa
biblioteca reprova sempre (`download_missing_libraries` é API proibida por
contrato — docs/28 §3, docs/32 §5, fato medido: ela faz rede). Nenhuma
checagem usa a biblioteca `jsonschema` — são reimplementadas aqui,
explicitamente, pelo mesmo motivo do módulo irmão `spec/validator.py`: o
contrato desta frente pede validação sem nova dependência externa.

Este módulo NUNCA levanta em entrada malformada (`None`, lista, string,
inteiro, bool, dict com formas erradas) — sempre devolve um
`RegistryValidationResult` com `problems` preenchido. Quem decide interromper
um fluxo a partir disso é o chamador.

DECISÃO CENTRAL DESTE SLICE — por que `node_path` é amarrado ao `sha256`
=========================================================================
`application_node_path` é um caminho de ÍNDICES, não de nomes (medido em
docs/32 §"Por que W1.4 volta ao projeto-base" e docs/33 §7: um cartão de I/O
acrescentado sob o `Device` desloca índices e faz `root/1/0/0` deixar de
apontar para o `Application`). Isso significa que um `node_path` só é válido
para o ARQUIVO EXATO sobre o qual foi medido — nunca para "o template" como
conceito abstrato, porque duas cópias do "mesmo" template (versões
diferentes, cartões de I/O diferentes) podem ter árvores com formas
diferentes por baixo do mesmo nome.

Este módulo torna esse vínculo estruturalmente difícil de quebrar por
acidente de duas formas:

1. Cada `TemplateEntry` carrega `sha256` e `application_node_path` juntos,
   no mesmo objeto imutável — não existe API que devolva um `node_path` sem
   também devolver (ou exigir) o `sha256` ao qual ele pertence.
2. A única forma pública de obter um `node_path` a partir de um arquivo real
   é `resolve_node_path_for_file`, que recebe o sha256 REALMENTE computado
   do arquivo em mãos e só devolve o node_path se ele bater com uma entrada
   do registry. Não existe atalho por `template_id`: dois templates com o
   mesmo `template_id` (ex.: duas versões do mesmo template) mas sha256 diferentes
   têm, corretamente, `node_path`s tratados como independentes — pedir pelo
   nome não devolve node_path nenhum, só pedir pelo hash do arquivo devolve.

Isso NÃO impede um chamador de ignorar `resolve_node_path_for_file` e usar
`entry.application_node_path` diretamente sem checar o sha256 do arquivo em
mãos — Python não tem como proibir isso de forma absoluta. O que este módulo
garante é que o caminho "correto" (resolver por sha256) existe, é o único
documentado, e o caminho "errado" (node_path sem checar sha256) exige o
chamador ignorar deliberadamente a API oferecida — a violação deixa de ser
um deslize por conveniência e passa a ser uma escolha explícita.

LACUNAS REGISTRADAS APÓS W1.3B (fatos medidos por outra frente, respeitados
aqui sem reinvenção)
=========================================================================
`persistent_tree_sha256` cobre UM NÍVEL, não a árvore inteira. Os probes de
W1.3B capturam a árvore via `get_children(False)` — só filhos diretos do
container, não recursivamente. Este módulo mantém o nome
`persistent_tree_sha256` porque é o nome exigido pelo contrato desta frente,
mas o escopo real (um nível) está documentado explicitamente aqui e no
schema (`template_registry.schema.json` §`persistent_tree_sha256`) para que
nenhum consumidor presuma cobertura recursiva que o dado não tem. Ampliar
para uma varredura recursiva real é trabalho de medição futura, não deste
slice.

Este módulo NÃO lê nem presume a `language` de nenhum objeto já existente no
template. Fato medido por outra frente: não há API catalogada para LER a
linguagem de um objeto existente no MasterTool X — `language` só aparece
como parâmetro de ENTRADA de `create_*`. Por isso `TemplateEntry` não carrega
nenhum campo "linguagem dos objetos existentes"; seria dado que a API não
oferece meio de medir.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

SCHEMA_VERSION = 1

_SHA256_RE = re.compile(r"^[0-9a-fA-F]{64}$")
_GUID_RE = re.compile(
    r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-"
    r"[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$")
_NODE_PATH_RE = re.compile(r"^root(/[0-9]+)*$")

# Mesmo vocabulário fechado de famílias de `mastertool_bridge.spec.validator`
# — reaproveitado aqui para que `authoring_rules.allowed_object_families`
# fale a mesma língua que `project_spec`, sem reinventar nomes.
_KNOWN_OBJECT_FAMILIES = frozenset({
    "duts", "gvls", "functions", "function_blocks", "programs",
    "tasks", "libraries",
})

_TEMPLATE_ENTRY_REQUIRED = frozenset({
    "template_id", "mastertool_version", "sha256", "size_bytes",
    "application_node_path", "application_type_guid", "compiler_version",
    "persistent_tree_sha256", "libraries", "tasks", "volatile_fields",
    "reserved_object_names", "authoring_rules",
})

_LIBRARY_REQUIRED = frozenset({"name", "allow_download"})
_LIBRARY_OPTIONAL = frozenset({"version", "sha256"})
_LIBRARY_ALLOWED = _LIBRARY_REQUIRED | _LIBRARY_OPTIONAL

_TASK_REQUIRED = frozenset({"name"})
_TASK_OPTIONAL = frozenset({"cycle_time_ms", "priority"})
_TASK_ALLOWED = _TASK_REQUIRED | _TASK_OPTIONAL

_AUTHORING_RULES_REQUIRED = frozenset({"allowed_object_families", "forbidden_apis"})

_TOP_LEVEL_KNOWN_KEYS = frozenset({"schema_version", "templates"})


class RegistryValidationError(ValueError):
    """Reservado para uso futuro por chamadores que queiram transformar
    `problems` em exceção. `validate_template_registry` nunca a levanta."""


@dataclass(frozen=True)
class LibraryRef:
    name: str
    version: str | None = None
    sha256: str | None = None
    allow_download: bool = False


@dataclass(frozen=True)
class TaskRef:
    name: str
    cycle_time_ms: float | None = None
    priority: int | None = None


@dataclass(frozen=True)
class AuthoringRules:
    allowed_object_families: tuple[str, ...] = field(default_factory=tuple)
    forbidden_apis: tuple[str, ...] = field(default_factory=tuple)


EVIDENCE_MEASURED = "measured"
EVIDENCE_UNRESOLVED = "unresolved"
EVIDENCE_STATUSES = (EVIDENCE_MEASURED, EVIDENCE_UNRESOLVED)

BLOCKER_COMPILER_VERSION = "compiler_version_unresolved"

QUALIFICATION_QUALIFIED = "qualified"
QUALIFICATION_WITH_BLOCKERS = "qualified_with_blockers"


@dataclass(frozen=True)
class Evidence:
    """Um campo que pode ser **medido** ou ser uma **lacuna comprovada**.

    Existe porque um escalar não consegue distinguir três coisas que precisam
    ser distinguidas: valor medido, valor não aplicável e valor que ninguém
    conseguiu ler. `None` e string vazia colapsam as três, e é assim que uma
    lacuna atravessa fronteira se passando por dado.
    """

    status: str
    value: str | None
    source: str
    reason: str | None

    @property
    def is_measured(self) -> bool:
        return self.status == EVIDENCE_MEASURED


@dataclass(frozen=True)
class TemplateEntry:
    """Uma entrada validada do registry. `application_node_path` só é válido
    em conjunto com `sha256` — ver docstring do módulo. Não existe construtor
    que aceite um sem o outro: os dois vêm sempre juntos, do mesmo objeto.

    `authoring_eligible` é **derivado**, nunca lido do arquivo: um registry que
    pudesse se declarar elegível seria exatamente o modo de falha que este
    modelo existe para impedir — a mesma razão pela qual um plano não pode
    declarar a própria fase autorizada.
    """

    template_id: str
    mastertool_version: str
    sha256: str
    size_bytes: int
    application_node_path: str
    application_type_guid: str
    compiler_version: Evidence
    qualification_status: str
    authoring_eligible: bool
    blocking_issues: tuple[str, ...]
    persistent_tree_sha256: str
    libraries: tuple[LibraryRef, ...]
    tasks: tuple[TaskRef, ...]
    volatile_fields: tuple[str, ...]
    reserved_object_names: tuple[str, ...]
    authoring_rules: AuthoringRules


@dataclass
class RegistryValidationResult:
    """Resultado de `validate_template_registry`.

    `problems` vazio é a única condição de sucesso. `entries_by_sha256` e
    `entries_by_template_id` são devolvidos com o melhor esforço mesmo
    quando há problemas, mas só devem ser usados por um chamador quando
    `problems == []` — o mesmo contrato de `spec.validator.ValidationResult`.
    """

    problems: list[str] = field(default_factory=list)
    entries_by_sha256: dict[str, TemplateEntry] = field(default_factory=dict)
    entries_by_template_id: dict[str, list[TemplateEntry]] = field(default_factory=dict)

    @property
    def ok(self) -> bool:
        return not self.problems


def _validate_library(index: int, obj: Any, problems: list[str]) -> LibraryRef | None:
    location = f"libraries[{index}]"
    if not isinstance(obj, dict):
        problems.append(
            f"{location}: deve ser um objeto (dict), recebido "
            f"{type(obj).__name__}.")
        return None

    unknown = set(obj.keys()) - _LIBRARY_ALLOWED
    if unknown:
        problems.append(
            f"{location}: campo(s) desconhecido(s), fail-closed: "
            + ", ".join(sorted(unknown)))

    missing = _LIBRARY_REQUIRED - set(obj.keys())
    if missing:
        problems.append(
            f"{location}: campo(s) obrigatório(s) ausente(s): "
            + ", ".join(sorted(missing)))
        return None

    name = obj.get("name")
    if not isinstance(name, str) or not name:
        problems.append(f"{location}.name: deve ser string não vazia.")
        return None

    allow_download = obj.get("allow_download")
    if allow_download is not False:
        problems.append(
            f"{location} ('{name}').allow_download: deve ser sempre "
            f"false, recebido {allow_download!r} — "
            "download_missing_libraries é API proibida por contrato "
            "(faz rede, docs/28 §3), e um registry que declare "
            "allow_download=true estaria descrevendo uma capacidade que "
            "nenhuma sessão tem permissão de exercer.")

    version = obj.get("version")
    if version is not None and not isinstance(version, str):
        problems.append(f"{location} ('{name}').version: deve ser string.")
        version = None

    sha256 = obj.get("sha256")
    if sha256 is not None and (not isinstance(sha256, str) or not _SHA256_RE.match(sha256)):
        problems.append(
            f"{location} ('{name}').sha256: deve ser um SHA-256 hex de 64 "
            "caracteres.")
        sha256 = None

    return LibraryRef(
        name=name,
        version=version,
        sha256=sha256,
        allow_download=False if allow_download is False else bool(allow_download),
    )


def _validate_task(index: int, obj: Any, problems: list[str]) -> TaskRef | None:
    location = f"tasks[{index}]"
    if not isinstance(obj, dict):
        problems.append(
            f"{location}: deve ser um objeto (dict), recebido "
            f"{type(obj).__name__}.")
        return None

    unknown = set(obj.keys()) - _TASK_ALLOWED
    if unknown:
        problems.append(
            f"{location}: campo(s) desconhecido(s), fail-closed: "
            + ", ".join(sorted(unknown)))

    missing = _TASK_REQUIRED - set(obj.keys())
    if missing:
        problems.append(
            f"{location}: campo(s) obrigatório(s) ausente(s): "
            + ", ".join(sorted(missing)))
        return None

    name = obj.get("name")
    if not isinstance(name, str) or not name:
        problems.append(f"{location}.name: deve ser string não vazia.")
        return None

    cycle_time_ms = obj.get("cycle_time_ms")
    if cycle_time_ms is not None:
        if isinstance(cycle_time_ms, bool) or not isinstance(cycle_time_ms, (int, float)) \
                or cycle_time_ms <= 0:
            problems.append(
                f"{location} ('{name}').cycle_time_ms: deve ser número > 0.")
            cycle_time_ms = None

    priority = obj.get("priority")
    if priority is not None:
        if isinstance(priority, bool) or not isinstance(priority, int) or priority < 0:
            problems.append(
                f"{location} ('{name}').priority: deve ser inteiro >= 0.")
            priority = None

    return TaskRef(name=name, cycle_time_ms=cycle_time_ms, priority=priority)


def _validate_authoring_rules(label: str, obj: Any, problems: list[str]) -> AuthoringRules:
    if not isinstance(obj, dict):
        problems.append(
            f"{label}.authoring_rules: deve ser um objeto, recebido "
            f"{type(obj).__name__ if obj is not None else 'ausente'}.")
        return AuthoringRules()

    unknown = set(obj.keys()) - _AUTHORING_RULES_REQUIRED
    if unknown:
        problems.append(
            f"{label}.authoring_rules: campo(s) desconhecido(s), "
            "fail-closed: " + ", ".join(sorted(unknown)))

    missing = _AUTHORING_RULES_REQUIRED - set(obj.keys())
    if missing:
        problems.append(
            f"{label}.authoring_rules: campo(s) obrigatório(s) ausente(s): "
            + ", ".join(sorted(missing)))

    families = obj.get("allowed_object_families")
    if not isinstance(families, list) or not all(isinstance(f, str) for f in families):
        problems.append(
            f"{label}.authoring_rules.allowed_object_families: deve ser "
            "lista de strings.")
        families = []
    else:
        unknown_families = [f for f in families if f not in _KNOWN_OBJECT_FAMILIES]
        if unknown_families:
            problems.append(
                f"{label}.authoring_rules.allowed_object_families: "
                "família(s) desconhecida(s): " + ", ".join(sorted(unknown_families))
                + " — famílias válidas: " + ", ".join(sorted(_KNOWN_OBJECT_FAMILIES)))

    forbidden_apis = obj.get("forbidden_apis")
    if not isinstance(forbidden_apis, list) or not all(isinstance(a, str) and a for a in forbidden_apis):
        problems.append(
            f"{label}.authoring_rules.forbidden_apis: deve ser lista de "
            "strings não vazias.")
        forbidden_apis = []

    return AuthoringRules(
        allowed_object_families=tuple(families),
        forbidden_apis=tuple(forbidden_apis),
    )


_EVIDENCE_FIELDS = ("status", "value", "source", "reason")


def _validate_evidence(label: str, obj: Any, problems: list[str]) -> Evidence:
    """Valida um campo de evidência, nas DUAS direções.

    `measured` exige valor textual não vazio; `unresolved` exige `value: null`
    e razão escrita, e **proíbe** valor preenchido. Checar só uma direção
    deixaria passar o caso pior: `unresolved` carregando um valor, que é uma
    lacuna se anunciando como lacuna enquanto entrega dado que ninguém mediu.
    """
    ruim = Evidence(status=EVIDENCE_UNRESOLVED, value=None,
                    source="invalid", reason="entrada inválida")
    if not isinstance(obj, dict):
        problems.append(
            f"{label}: deve ser um objeto de evidência com "
            f"{{status, value, source, reason}} — um escalar não distingue "
            "valor medido de lacuna.")
        return ruim

    desconhecidos = sorted(k for k in obj if k not in _EVIDENCE_FIELDS)
    if desconhecidos:
        problems.append(
            f"{label}: campo(s) desconhecido(s), fail-closed: "
            f"{', '.join(desconhecidos)}")

    status = obj.get("status")
    if status not in EVIDENCE_STATUSES:
        problems.append(
            f"{label}.status: deve ser um de {list(EVIDENCE_STATUSES)}, "
            f"recebido {status!r}.")
        return ruim

    value = obj.get("value")
    source = obj.get("source")
    reason = obj.get("reason")

    if not isinstance(source, str) or not source:
        problems.append(f"{label}.source: deve ser string não vazia — a "
                        "evidência precisa dizer de onde veio.")

    if status == EVIDENCE_MEASURED:
        if not isinstance(value, str) or not value:
            problems.append(
                f"{label}: status 'measured' exige value string não vazia. "
                "String vazia com status 'measured' é pior que a lacuna, "
                "porque a lacuna ao menos se anuncia.")
    else:
        if value is not None:
            problems.append(
                f"{label}: status 'unresolved' exige value null, recebido "
                f"{value!r}. Lacuna que carrega valor entrega dado que "
                "ninguém mediu.")
        if not isinstance(reason, str) or not reason:
            problems.append(
                f"{label}: status 'unresolved' exige reason não vazia — "
                "lacuna sem razão escrita é indistinguível de esquecimento.")

    return Evidence(
        status=status,
        value=value if isinstance(value, str) and value else None,
        source=source if isinstance(source, str) else "",
        reason=reason if isinstance(reason, str) and reason else None,
    )


def _derive_eligibility(compiler_version: Evidence) -> tuple[str, bool, tuple[str, ...]]:
    """Qualificação e elegibilidade são CONSEQUÊNCIA, não declaração.

    Não há parâmetro vindo do arquivo. Se o registry pudesse afirmar
    `authoring_eligible: true`, bastaria alguém escrever isso para liberar
    execução mutável sobre um template incompleto.
    """
    blockers: list[str] = []
    if not compiler_version.is_measured:
        blockers.append(BLOCKER_COMPILER_VERSION)
    if blockers:
        return QUALIFICATION_WITH_BLOCKERS, False, tuple(blockers)
    return QUALIFICATION_QUALIFIED, True, ()


def _validate_template_entry(index: int, obj: Any, problems: list[str]) -> TemplateEntry | None:
    location = f"templates[{index}]"
    if not isinstance(obj, dict):
        problems.append(
            f"{location}: deve ser um objeto (dict), recebido "
            f"{type(obj).__name__}.")
        return None

    unknown = set(obj.keys()) - _TEMPLATE_ENTRY_REQUIRED
    if unknown:
        problems.append(
            f"{location}: campo(s) desconhecido(s), fail-closed: "
            + ", ".join(sorted(unknown)))

    missing = _TEMPLATE_ENTRY_REQUIRED - set(obj.keys())
    if missing:
        problems.append(
            f"{location}: campo(s) obrigatório(s) ausente(s): "
            + ", ".join(sorted(missing)))
        return None

    template_id = obj.get("template_id")
    if not isinstance(template_id, str) or not template_id:
        problems.append(f"{location}.template_id: deve ser string não vazia.")
        return None

    label = f"templates.{template_id}[{index}]"

    mastertool_version = obj.get("mastertool_version")
    if not isinstance(mastertool_version, str) or not mastertool_version:
        problems.append(f"{label}.mastertool_version: deve ser string não vazia.")

    sha256 = obj.get("sha256")
    if not isinstance(sha256, str) or not _SHA256_RE.match(sha256):
        problems.append(f"{label}.sha256: deve ser um SHA-256 hex de 64 caracteres.")
        sha256 = None

    size_bytes = obj.get("size_bytes")
    if isinstance(size_bytes, bool) or not isinstance(size_bytes, int) or size_bytes < 0:
        problems.append(f"{label}.size_bytes: deve ser inteiro >= 0.")
        size_bytes = None

    node_path = obj.get("application_node_path")
    if not isinstance(node_path, str) or not _NODE_PATH_RE.match(node_path):
        problems.append(
            f"{label}.application_node_path: deve casar com "
            r"'^root(/[0-9]+)*$'"
            f" (caminho de ÍNDICES, ex. 'root/1/0/0'), recebido {node_path!r}.")
        node_path = None

    type_guid = obj.get("application_type_guid")
    if not isinstance(type_guid, str) or not _GUID_RE.match(type_guid):
        problems.append(
            f"{label}.application_type_guid: deve ser um GUID válido no "
            "formato 8-4-4-4-12.")
        type_guid = None

    compiler_version = _validate_evidence(
        f"{label}.compiler_version", obj.get("compiler_version"), problems)

    persistent_tree_sha256 = obj.get("persistent_tree_sha256")
    if not isinstance(persistent_tree_sha256, str) or not _SHA256_RE.match(persistent_tree_sha256):
        problems.append(
            f"{label}.persistent_tree_sha256: deve ser um SHA-256 hex de "
            "64 caracteres.")

    raw_libraries = obj.get("libraries")
    libraries: list[LibraryRef] = []
    if not isinstance(raw_libraries, list):
        problems.append(f"{label}.libraries: deve ser uma lista.")
    else:
        for i, lib in enumerate(raw_libraries):
            validated = _validate_library(i, lib, problems)
            if validated is not None:
                libraries.append(validated)

    raw_tasks = obj.get("tasks")
    tasks: list[TaskRef] = []
    if not isinstance(raw_tasks, list):
        problems.append(f"{label}.tasks: deve ser uma lista.")
    else:
        for i, task in enumerate(raw_tasks):
            validated = _validate_task(i, task, problems)
            if validated is not None:
                tasks.append(validated)

    volatile_fields = obj.get("volatile_fields")
    if not isinstance(volatile_fields, list) or not all(
            isinstance(v, str) and v for v in volatile_fields):
        problems.append(
            f"{label}.volatile_fields: deve ser lista de strings não "
            "vazias (nomes/caminhos de campo ignorados pelo diff).")
        volatile_fields = []

    reserved_object_names = obj.get("reserved_object_names")
    if not isinstance(reserved_object_names, list) or not all(
            isinstance(n, str) and n for n in reserved_object_names):
        problems.append(
            f"{label}.reserved_object_names: deve ser lista de strings não "
            "vazias.")
        reserved_object_names = []

    authoring_rules = _validate_authoring_rules(label, obj.get("authoring_rules"), problems)

    if sha256 is None or node_path is None or type_guid is None or size_bytes is None:
        return None

    qualification, eligible, blockers = _derive_eligibility(compiler_version)

    # Se o arquivo DECLARAR elegibilidade, isso e contradicao -- nao dado. A
    # verificacao existe porque o campo derivado e o unico que o executor
    # consulta: aceitar a declaracao seria devolver ao autor do registry o
    # poder que o modelo acabou de tirar dele.
    for campo, derivado in (("qualification_status", qualification),
                            ("authoring_eligible", eligible),
                            ("blocking_issues", list(blockers))):
        if campo in obj and obj[campo] != derivado:
            problems.append(
                f"{label}.{campo}: é DERIVADO e não pode ser declarado. "
                f"O arquivo diz {obj[campo]!r}, a derivação diz {derivado!r}. "
                "Um registry que se auto-declara elegível é exatamente o modo "
                "de falha que este modelo existe para impedir.")

    return TemplateEntry(
        template_id=template_id,
        mastertool_version=mastertool_version if isinstance(mastertool_version, str) else "",
        sha256=sha256,
        size_bytes=size_bytes,
        application_node_path=node_path,
        application_type_guid=type_guid,
        compiler_version=compiler_version,
        qualification_status=qualification,
        authoring_eligible=eligible,
        blocking_issues=blockers,
        persistent_tree_sha256=persistent_tree_sha256
        if isinstance(persistent_tree_sha256, str) else "",
        libraries=tuple(libraries),
        tasks=tuple(tasks),
        volatile_fields=tuple(volatile_fields),
        reserved_object_names=tuple(reserved_object_names),
        authoring_rules=authoring_rules,
    )


def validate_template_registry(data: Any) -> RegistryValidationResult:
    """Valida `template_registry` offline. NUNCA levanta exceção — entrada
    degenerada (`None`, lista, string, inteiro, bool, dict malformado em
    qualquer nível) sempre produz um `RegistryValidationResult` com
    `problems` preenchido."""
    problems: list[str] = []

    if not isinstance(data, dict):
        problems.append(
            "template_registry deve ser um objeto (dict) no nível raiz, "
            f"recebido {type(data).__name__}.")
        return RegistryValidationResult(problems=problems)

    unknown_top = set(data.keys()) - _TOP_LEVEL_KNOWN_KEYS
    if unknown_top:
        problems.append(
            "template_registry contém chave(s) desconhecida(s) no nível "
            "raiz, fail-closed: " + ", ".join(sorted(unknown_top)))

    schema_version = data.get("schema_version")
    if schema_version != SCHEMA_VERSION:
        problems.append(
            f"schema_version deve ser {SCHEMA_VERSION}, recebido "
            f"{schema_version!r}.")

    raw_templates = data.get("templates")
    entries: list[TemplateEntry] = []
    if not isinstance(raw_templates, list):
        problems.append("templates: deve ser uma lista.")
    else:
        for i, entry in enumerate(raw_templates):
            validated = _validate_template_entry(i, entry, problems)
            if validated is not None:
                entries.append(validated)

    # sha256 é a chave de verdade: `application_node_path` só é válido para o
    # arquivo exato que produziu aquele sha256 (ver docstring do módulo).
    # Duas entradas com o mesmo sha256 estariam descrevendo o MESMO arquivo
    # duas vezes — se concordam, é redundante; se divergem (node_path
    # diferente, por exemplo), é uma contradição que nenhum chamador pode
    # resolver sozinho, e por isso reprova.
    entries_by_sha256: dict[str, TemplateEntry] = {}
    for entry in entries:
        existing = entries_by_sha256.get(entry.sha256)
        if existing is None:
            entries_by_sha256[entry.sha256] = entry
        elif existing != entry:
            problems.append(
                f"templates: sha256 '{entry.sha256}' aparece em mais de "
                "uma entrada com dados divergentes — um arquivo só pode "
                "ter uma descrição de template, porque node_path só é "
                "válido para o arquivo exato que ele descreve.")
        # entradas idênticas (mesmo sha256, mesmos dados) são redundância
        # inofensiva, não erro — mas não substituem a primeira no dict.

    entries_by_template_id: dict[str, list[TemplateEntry]] = {}
    for entry in entries:
        entries_by_template_id.setdefault(entry.template_id, []).append(entry)

    return RegistryValidationResult(
        problems=problems,
        entries_by_sha256=entries_by_sha256,
        entries_by_template_id=entries_by_template_id,
    )


def resolve_node_path_for_file(
        result: RegistryValidationResult, file_sha256: str) -> str | None:
    """Única forma pública de obter um `application_node_path` a partir de
    um arquivo real: o chamador precisa ter computado o sha256 do arquivo em
    mãos e passá-lo aqui. Devolve `None` se `result` tem problemas, se
    `file_sha256` não é um SHA-256 válido, ou se nenhuma entrada do registry
    descreve exatamente esse arquivo — nos três casos, o chamador NÃO recebe
    um node_path de outra entrada por engano, porque não existe fallback
    "quase igual" ou "por template_id" nesta função.

    Isso é a materialização da decisão central deste módulo: node_path é
    válido para UM arquivo (identificado por sha256), nunca para "o
    template" como conceito — pedir por template_id não é uma opção
    oferecida por esta API."""
    if not result.ok:
        return None
    if not isinstance(file_sha256, str) or not _SHA256_RE.match(file_sha256):
        return None
    entry = result.entries_by_sha256.get(file_sha256)
    if entry is None:
        return None
    return entry.application_node_path


def select_template_for_authoring(
        result: RegistryValidationResult, file_sha256: str) -> TemplateEntry | None:
    """Único caminho pelo qual um executor mutável pode escolher um template.

    Recusa — devolvendo `None` — quando o template existe e foi medido mas
    **não é elegível para autoria**. Essa é a razão de a função existir
    separada de `resolve_node_path_for_file`: inspecionar um template
    incompleto é legítimo e continua permitido; **executar** sobre ele não é.

        template qualificado estruturalmente  !=  template elegível

    Um `TemplateEntry` com `authoring_eligible = False` nunca sai daqui, e
    `authoring_eligible` não pode ter sido escrito no arquivo — ele é derivado
    dos bloqueios. Assim não há como liberar execução editando o registry.
    """
    if not result.ok:
        return None
    if not isinstance(file_sha256, str) or not _SHA256_RE.match(file_sha256):
        return None
    entry = result.entries_by_sha256.get(file_sha256)
    if entry is None:
        return None
    if not entry.authoring_eligible:
        return None
    return entry


def authoring_refusal_reason(
        result: RegistryValidationResult, file_sha256: str) -> str | None:
    """Por que `select_template_for_authoring` recusou, em texto.

    Recusa silenciosa é indistinguível de template ausente, e as duas exigem
    ações opostas: uma manda medir o que falta, a outra manda registrar o
    template. Devolve `None` quando não houve recusa.
    """
    if not result.ok:
        return "registry inválido: %d problema(s)" % len(result.problems)
    if not isinstance(file_sha256, str) or not _SHA256_RE.match(file_sha256):
        return "sha256 inválido: não é hex de 64 caracteres"
    entry = result.entries_by_sha256.get(file_sha256)
    if entry is None:
        return "nenhuma entrada do registry descreve o arquivo %s" % file_sha256
    if not entry.authoring_eligible:
        return ("template '%s' está qualificado mas NÃO é elegível para "
                "autoria; bloqueios pendentes: %s"
                % (entry.template_id, ", ".join(entry.blocking_issues)))
    return None


def check_reserved_object_names(
        entry: TemplateEntry, proposed_names: Any) -> list[str]:
    """Devolve a lista de nomes em `proposed_names` que colidem com
    `entry.reserved_object_names` — nomes que já existem no template e que
    uma `project_spec` não pode tentar (re)criar (ex.: GVL_AI_TESTE,
    PRG_AI_TESTE deixados por uma execução anterior sobre o mesmo template).
    Lista vazia significa "nenhum conflito". Entrada degenerada em
    `proposed_names` (não iterável de strings) devolve lista vazia — quem
    decide bloquear a sessão por causa disso é o chamador, comparando com o
    total de nomes propostos."""
    if not isinstance(proposed_names, (list, tuple, set, frozenset)):
        return []
    reserved = set(entry.reserved_object_names)
    return sorted({
        name for name in proposed_names
        if isinstance(name, str) and name in reserved
    })

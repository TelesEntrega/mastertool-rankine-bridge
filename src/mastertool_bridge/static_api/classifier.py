"""Classificação CONSERVADORA de membros (.NET) descobertos por reflection
estática, em quatro categorias:

    read_candidate      leitura, sem indício de efeito colateral
    write_candidate      indício de mutação (nome, ou propriedade com setter)
    online_candidate     indício de operação online/comunicação
    unknown               não claramente somente leitura — nunca promovido
                          a read_candidate por falta de evidência

Regra de ouro (pedida explicitamente): nunca classificar segurança apenas
pelo nome do método quando o nome for ambíguo — qualquer coisa não
claramente somente leitura fica `unknown` ou `write_candidate`, nunca
`read_candidate` por omissão.
"""

from __future__ import annotations

READ_CANDIDATE = "read_candidate"
WRITE_CANDIDATE = "write_candidate"
ONLINE_CANDIDATE = "online_candidate"
UNKNOWN = "unknown"

# Substrings (case-insensitive) fortemente associadas a mutação. Qualquer
# ocorrência classifica o método como write_candidate, mesmo que o nome
# também pareça "de leitura" (ex.: "export_xml" grava arquivo).
WRITE_NAME_SUBSTRINGS = (
    "save", "close", "remove", "rename", "move", "insert", "append",
    "replace", "add", "create", "open", "import", "export", "convert",
    "document", "build", "rebuild", "clean", "generate_code", "execute",
    "clear", "delete", "write", "set_",
)

# Substrings associadas a operação online/comunicação — categoria à parte,
# checada ANTES de write (prioridade: online é o risco mais alto).
ONLINE_NAME_SUBSTRINGS = (
    "online", "download", "login", "force", "start", "stop", "reset",
    "connect", "gateway", "scan", "boot_application",
)

# Nomes de método promovidos a read_candidate — SÓ por evidência concreta
# (observados nesta rodada de reflection estática, ver
# docs/api/mastertool-api-observations.md), nunca por suposição genérica.
KNOWN_READ_METHOD_NAMES = frozenset([
    "get_children", "find", "get_name", "get_line", "get_text",
    "tostring", "equals", "gethashcode", "gettype",
])

# Tipos .NET escalares simples — únicos tipos de propriedade promovidos a
# read_candidate (quando sem setter). Tipos complexos/coleções/Object ficam
# unknown por padrão, mesmo sem setter.
_SIMPLE_PROPERTY_TYPES = frozenset([
    "system.string", "system.boolean", "system.int16", "system.int32",
    "system.int64", "system.guid",
])


def _contains_any(text, substrings):
    lowered = text.lower()
    return any(sub in lowered for sub in substrings)


def classify_method(name):
    """Classifica um método pelo nome. Retorna uma das 4 categorias."""
    if _contains_any(name, ONLINE_NAME_SUBSTRINGS):
        return ONLINE_CANDIDATE
    if _contains_any(name, WRITE_NAME_SUBSTRINGS):
        return WRITE_CANDIDATE
    if name.lower() in KNOWN_READ_METHOD_NAMES:
        return READ_CANDIDATE
    return UNKNOWN


def classify_property(name, can_write, prop_type=None):
    """Classifica uma propriedade. `can_write=True` sempre vira
    write_candidate (mesmo que a leitura em si seja provavelmente segura —
    ver `property_note`)."""
    if can_write:
        return WRITE_CANDIDATE
    if _contains_any(name, ONLINE_NAME_SUBSTRINGS):
        return ONLINE_CANDIDATE
    if prop_type and prop_type.split("[")[0].lower() in _SIMPLE_PROPERTY_TYPES:
        return READ_CANDIDATE
    return UNKNOWN


def property_note(can_read, can_write):
    """Nota explicativa para propriedades com leitura E escrita — o getter
    isoladamente é provavelmente seguro, mas a categoria geral do membro
    continua write_candidate (não distinguimos get/set na categoria)."""
    if can_read and can_write:
        return ("Propriedade tem getter E setter; a LEITURA isolada e "
                "provavelmente segura, mas o membro e classificado como "
                "write_candidate porque o setter existe.")
    return None


def classify_type_members(type_entry):
    """Classifica todos os métodos e propriedades de um type_entry (dict do
    catálogo bruto). Retorna uma cópia anotada com 'classification' em cada
    método/propriedade."""
    result = dict(type_entry)
    result["properties"] = []
    for prop in type_entry.get("properties", []):
        annotated = dict(prop)
        annotated["classification"] = classify_property(
            prop["name"], prop.get("can_write", False), prop.get("type"))
        note = property_note(prop.get("can_read", False), prop.get("can_write", False))
        if note:
            annotated["note"] = note
        result["properties"].append(annotated)

    result["methods"] = []
    for method in type_entry.get("methods", []):
        annotated = dict(method)
        annotated["classification"] = classify_method(method["name"])
        result["methods"].append(annotated)
    return result

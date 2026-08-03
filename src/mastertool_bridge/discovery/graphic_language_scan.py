"""Fase L0 (offline) do roadmap Ladder/FBD/SFC — `docs/14-ladder-roadmap.md`.

Classifica, de forma PURAMENTE determinística, cada objeto de um export já
validado do `ReadOnlyTextExporter` (`flat-objects.json`) em um de 4 estados
(`supported` / `partially_supported` / `unsupported` / `unknown`), usando
SOMENTE os campos já capturados — nenhum acesso ao MasterTool, nenhuma
suposição sobre API não confirmada, nenhuma tentativa de interpretar o
CONTEÚDO de uma implementação gráfica (isso é L1+, fora de escopo aqui).

Ideia central: um `type_guid` que aparece em pelo menos um objeto com
`has_implementation=true` em QUALQUER lugar do projeto é "um tipo de objeto
que sabemos ter implementação textual em algum lugar" — se outro objeto do
MESMO `type_guid` tem declaração mas NÃO tem implementação, isso é evidência
(não prova) de que a lógica dele existe em forma NÃO textual (candidato a
Ladder/FBD/SFC). Esse conjunto de referência é sempre DERIVADO em tempo de
execução a partir do próprio export — nunca hardcoded.

Este módulo nunca afirma que um candidato É Ladder/FBD/SFC especificamente
— apenas "candidato a implementação não textual". Confirmar a linguagem
real exige uma execução dentro do MasterTool (fora do escopo desta fatia).

Nota honesta sobre `is_folder`: `flat-objects.json` (o único artefato que
esta fatia está autorizada a consumir) NÃO contém um campo booleano
"é pasta" confiável — confirmado por inspeção cruzada com
`application-tree.json`/`metadata.json` (que carregam `identity.is_folder`,
fora do escopo de entrada desta fatia): tanto pastas de organização quanto
containers não-pasta (ex. "Task Configuration") têm `has_declaration=false`,
`has_implementation=false` e `type_guid` preenchido, então nenhuma
combinação dos campos de `flat-objects.json` distingue os dois casos sem
recorrer a um `type_guid` específico hardcoded (proibido). Por isso
`is_folder` é reportado como `None` (desconhecido) nos artefatos desta
fatia — nunca adivinhado.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from mastertool_bridge.utils.json_io import read_json, write_json

SUPPORTED = "supported"
PARTIALLY_SUPPORTED = "partially_supported"
UNSUPPORTED = "unsupported"
UNKNOWN = "unknown"


def scan_graphic_language_candidates(export_dir: Path, output_dir: Path) -> dict[str, Any]:
    """Lê `flat-objects.json` de `export_dir`, classifica cada objeto e
    escreve 3 artefatos em `output_dir`:

        graphic-language-inventory.json  -- todos os objetos, com estado
        ladder-objects.json              -- subconjunto state=partially_supported
        unsupported-objects.json         -- subconjunto state=unsupported

    Retorna um dict resumo (mesmo padrão de `build_static_index`): escreve
    em disco E devolve os dados em memória, testável com `tmp_path` sem
    reler do disco.

    Determinístico: mesma entrada -> mesma saída byte-a-byte (ordenação
    estável por `node_id`, sem depender de ordem de iteração de dict/set).
    """
    export_dir = Path(export_dir)
    output_dir = Path(output_dir)

    flat_objects_path = export_dir / "flat-objects.json"
    flat_objects: list[dict[str, Any]] = []
    if flat_objects_path.is_file():
        flat_objects = read_json(flat_objects_path) or []

    inventory = _classify_objects(flat_objects)

    ladder_objects = [o for o in inventory if o["state"] == PARTIALLY_SUPPORTED]
    unsupported_objects = [o for o in inventory if o["state"] == UNSUPPORTED]

    write_json(output_dir / "graphic-language-inventory.json", inventory)
    write_json(output_dir / "ladder-objects.json", ladder_objects)
    write_json(output_dir / "unsupported-objects.json", unsupported_objects)

    counts = {
        SUPPORTED: sum(1 for o in inventory if o["state"] == SUPPORTED),
        PARTIALLY_SUPPORTED: len(ladder_objects),
        UNSUPPORTED: len(unsupported_objects),
        UNKNOWN: sum(1 for o in inventory if o["state"] == UNKNOWN),
    }

    return {
        "inventory": inventory,
        "ladder_objects": ladder_objects,
        "unsupported_objects": unsupported_objects,
        "counts": counts,
    }


def _classify_objects(flat_objects: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_node_id = {o.get("node_id"): o for o in flat_objects if o.get("node_id")}

    # Passo 2 do objetivo: conjunto de type_guid vistos em pelo menos um
    # objeto com has_implementation=true, DERIVADO do próprio export a cada
    # chamada — nunca hardcoded. Guarda também os node_ids que confirmaram
    # cada type_guid, para compor a evidência textual (ordenados para saída
    # determinística, independente da ordem de iteração de flat_objects).
    confirmed_textual_node_ids_by_type_guid: dict[str, list[str]] = {}
    for obj in flat_objects:
        type_guid = obj.get("type_guid")
        node_id = obj.get("node_id")
        if type_guid and node_id and bool(obj.get("has_implementation")):
            confirmed_textual_node_ids_by_type_guid.setdefault(type_guid, []).append(node_id)
    for node_ids in confirmed_textual_node_ids_by_type_guid.values():
        node_ids.sort()

    inventory = [
        _classify_object(obj, by_node_id, confirmed_textual_node_ids_by_type_guid)
        for obj in flat_objects
    ]
    inventory.sort(key=lambda o: o["node_id"])
    return inventory


def _classify_object(
    obj: dict[str, Any],
    by_node_id: dict[str, dict[str, Any]],
    confirmed_textual_node_ids_by_type_guid: dict[str, list[str]],
) -> dict[str, Any]:
    node_id = obj.get("node_id")
    name = obj.get("name")
    type_guid = obj.get("type_guid")
    has_declaration = bool(obj.get("has_declaration"))
    has_implementation = bool(obj.get("has_implementation"))

    state: str
    evidence: str

    if has_declaration and has_implementation:
        state = SUPPORTED
        evidence = "has_declaration=true e has_implementation=true (implementação textual confirmada)."
    elif not has_declaration:
        state = UNSUPPORTED
        evidence = (
            "has_declaration=false (sem cabeçalho de POU/DUT textual reconhecível "
            "neste export -- fora do escopo desta busca)."
        )
    else:
        # has_declaration=true, has_implementation=false: candidato em
        # potencial, decidido pela presença/ausência de referência de
        # comparação para o mesmo type_guid.
        confirming_node_ids = [
            nid
            for nid in confirmed_textual_node_ids_by_type_guid.get(type_guid, [])
            if nid != node_id
        ] if type_guid else []

        if confirming_node_ids:
            state = PARTIALLY_SUPPORTED
            evidence = (
                f"type_guid compartilhado com {len(confirming_node_ids)} "
                f"objeto(s) confirmado(s) como texto: {confirming_node_ids}"
            )
        else:
            state = UNKNOWN
            evidence = (
                "has_declaration=true e has_implementation=false, mas type_guid "
                f"({type_guid!r}) nao aparece em nenhum objeto com "
                "has_implementation=true neste export -- sem referencia de "
                "comparacao para classificar como candidato."
            )

    return {
        "node_id": node_id,
        "name": name,
        "type_guid": type_guid,
        "path": _build_path(node_id, by_node_id),
        "has_declaration": has_declaration,
        "has_implementation": has_implementation,
        "is_folder": None,
        "state": state,
        "evidence": evidence,
    }


def _build_path(node_id: str | None, by_node_id: dict[str, dict[str, Any]]) -> str | None:
    """Caminho na árvore como nomes separados por '/', da raiz até o
    objeto (ex. "application/Estruturas/Motor"). Segmentos sem `name`
    (a raiz `application` não tem `name` em flat-objects.json) usam o
    próprio `node_id` daquele nível como rótulo, para nunca produzir um
    segmento vazio/None silencioso."""
    if node_id is None:
        return None

    segments: list[str] = []
    seen: set[str] = set()
    current: str | None = node_id
    while current is not None:
        if current in seen:
            # Ciclo em parent_node_id (não deveria ocorrer em dado real,
            # mas nunca trava/loop infinito em dado malformado).
            break
        seen.add(current)
        obj = by_node_id.get(current)
        if obj is None:
            # parent_node_id aponta para um node_id ausente do próprio
            # export -- preserva o node_id bruto como segmento em vez de
            # omitir silenciosamente.
            segments.append(current)
            break
        label = obj.get("name") or current
        segments.append(label)
        current = obj.get("parent_node_id")

    segments.reverse()
    return "/".join(segments)

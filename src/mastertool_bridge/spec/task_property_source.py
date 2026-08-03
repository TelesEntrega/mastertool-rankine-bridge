"""O "antes medido" de uma PROPRIEDADE de task — a procedência que
`configure_existing_task` exige (fase R2).

Módulo puro, offline. É o irmão de `modification_source.py`, e mora separado
porque as duas coisas não têm a mesma forma: **um texto tem hash, uma
propriedade tem valor**. Comparar hash é comparar duas strings de 64 hex;
comparar valor exige saber que `None` não é um valor, e sim a ausência de
medição.

A FONTE EXISTE, E É READ-ONLY
=============================
`probes/42` lê `kind_of_task`, `priority`, `interval` e `interval_unit` numa
sessão SOMENTE LEITURA — as quatro estão catalogadas no stub oficial
`ScriptTaskObject.pyi` que o produto instala. Isso dá ao "antes" de uma
propriedade a mesma procedência que o "antes" de um texto tem: medição, e não
memória de quem escreveu a spec.

`watchdog` fica FORA. Ele tem receptor próprio (`ScriptWatchdog`) e nunca foi
exercido; incluí-lo aqui daria a impressão de que a comparação o cobre.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

SCHEMA_VERSION = 1

# As quatro propriedades MEDIDAS. A lista é a interseção do que `probes/42` lê
# com o que o executor sabe escrever — e não a união: uma propriedade legível e
# não escrevível não pertence a um vocabulário de alteração.
TASK_PROPERTIES = ("kind_of_task", "interval", "interval_unit", "priority")


@dataclass
class TaskPropertyInventory:
    project_sha256: str | None = None
    tasks: dict[str, dict[str, Any]] = field(default_factory=dict)
    problems: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.problems

    def get(self, task: str, prop: str) -> Any:
        return (self.tasks.get(task) or {}).get(prop)


@dataclass
class TaskModificationCheck:
    problems: list[str] = field(default_factory=list)
    verified: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.problems

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": SCHEMA_VERSION,
            "ok": self.ok,
            "verified": list(self.verified),
            "problems": list(self.problems),
        }


def load_task_property_inventory(payload: Any,
                                 project_sha256: str | None = None
                                 ) -> TaskPropertyInventory:
    """Lê o inventário de propriedades de uma sessão read-only.

    Forma aceita: `{"tasks": [{"name": ..., "kind_of_task": ..., ...}]}`.
    Inventário sem nenhuma task é recusado pelo mesmo motivo do de textos: um
    projeto que tem Task Configuration tem ao menos uma task, e o vazio é
    leitura falha — não "projeto sem tasks".
    """
    inventario = TaskPropertyInventory(project_sha256=project_sha256)
    if not isinstance(payload, dict):
        inventario.problems.append(
            "inventário de tasks: esperado objeto, recebido %s"
            % type(payload).__name__)
        return inventario

    tasks = payload.get("tasks")
    if not isinstance(tasks, list):
        inventario.problems.append(
            "inventário de tasks sem lista `tasks`: formato não reconhecido")
        return inventario

    for indice, task in enumerate(tasks):
        if not isinstance(task, dict):
            inventario.problems.append("tasks[%d]: esperado objeto" % indice)
            continue
        nome = task.get("name")
        if not isinstance(nome, str) or not nome:
            inventario.problems.append("tasks[%d]: `name` obrigatório" % indice)
            continue
        inventario.tasks[nome] = {
            prop: task.get(prop) for prop in TASK_PROPERTIES if prop in task}

    if not inventario.tasks and not inventario.problems:
        inventario.problems.append(
            "inventário de tasks vazio — leitura falha, não projeto sem tasks")
    return inventario


def verify_task_modifications(spec: Any,
                              inventory: Any) -> TaskModificationCheck:
    """Confere cada `expected_before` de propriedade contra o inventário.

    Propriedade que a spec quer alterar e que o inventário NÃO mediu é recusa:
    escrever por cima de um valor que ninguém leu é o mesmo erro do texto, com
    outro nome.
    """
    resultado = TaskModificationCheck()

    if not isinstance(inventory, TaskPropertyInventory) or not inventory.ok:
        motivo = (inventory.problems
                  if isinstance(inventory, TaskPropertyInventory)
                  else ["inventário inválido"])
        resultado.problems.append(
            "inventário de tasks inutilizável: " + "; ".join(motivo))
        return resultado

    if not isinstance(spec, dict):
        resultado.problems.append("spec: esperado objeto")
        return resultado

    entradas = spec.get("task_modifications", [])
    if not isinstance(entradas, list):
        resultado.problems.append("task_modifications: esperado lista")
        return resultado

    for indice, item in enumerate(entradas):
        rotulo = "task_modifications[%d]" % indice
        if not isinstance(item, dict):
            resultado.problems.append("%s: esperado objeto" % rotulo)
            continue

        nome = item.get("name")
        if nome not in inventory.tasks:
            resultado.problems.append(
                "%s: task %r não está no inventário medido — alterar o que "
                "não foi lido é escrever as cegas" % (rotulo, nome))
            continue

        anteriores = item.get("expected_before") or {}
        if not isinstance(anteriores, dict) or not anteriores:
            resultado.problems.append(
                "%s: `expected_before` obrigatório e não vazio — sem ele a "
                "alteração de propriedade é escrita cega" % rotulo)
            continue

        for prop in sorted(anteriores):
            declarado = anteriores[prop]
            if prop not in TASK_PROPERTIES:
                resultado.problems.append(
                    "%s: propriedade %r fora do vocabulário medido: %s"
                    % (rotulo, prop, ", ".join(TASK_PROPERTIES)))
                continue
            medido = inventory.get(nome, prop)
            if medido is None:
                # `None` é "não medido", nunca "igual a qualquer coisa".
                resultado.problems.append(
                    "%s: %s.%s não foi medido pelo inventário. Ausência de "
                    "medição não é igualdade" % (rotulo, nome, prop))
                continue
            if str(medido) != str(declarado):
                resultado.problems.append(
                    "%s: %s.%s — a spec declara %r e o inventário mediu %r"
                    % (rotulo, nome, prop, declarado, medido))
                continue
            resultado.verified.append("%s.%s" % (nome, prop))

    return resultado

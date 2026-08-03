"""A procedência do `expected_before_sha256` — de onde o hash anterior vem
(fase R2).

Módulo puro, offline. Ele fecha o laço que a fundação da R2 deixou aberto: o
executor confere o hash anterior, mas quem escreve a spec ainda podia digitá-lo
de memória. Um hash digitado de memória é um hash inventado com formato certo.

O QUE ESTE MÓDULO FAZ
=====================
Lê um **inventário de textos medido** — o artefato que uma sessão READ-ONLY
produz — e confere, contra ele, cada `expected_before_sha256` declarado nas
`modifications` de uma spec. Diverge, recusa. Falta o objeto no inventário,
recusa. Inventário de outro projeto, recusa.

Também sabe PREENCHER: dado o inventário, devolve as modificações com o hash
correto, para que o autor da spec não precise copiá-lo à mão. Preencher e
conferir são funções separadas de propósito — quem preenche não deve ser quem
aprova.

POR QUE ISTO É READ-ONLY, E POR QUE ISSO IMPORTA
================================================
Medir o texto atual de um objeto não muta nada, então o inventário sai de uma
sessão sem gate de escrita aberto. É a etapa mais barata da cadeia da R2, e é
a que torna a mais cara — a sessão de escrita — verificável antes de começar.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

SCHEMA_VERSION = 1

_SHA256_RE = re.compile(r"^[0-9a-fA-F]{64}$")


@dataclass(frozen=True)
class MeasuredText:
    """Um documento medido: o que existe hoje, e qual é o hash dele."""

    family: str
    name: str
    field_name: str
    sha256: str

    @property
    def key(self) -> tuple[str, str, str]:
        return (self.family, self.name, self.field_name)


@dataclass
class TextInventory:
    """Inventário lido de um artefato de sessão read-only."""

    project_sha256: str | None = None
    texts: dict[tuple[str, str, str], MeasuredText] = field(default_factory=dict)
    problems: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.problems

    def get(self, family: str, name: str, field_name: str) -> MeasuredText | None:
        return self.texts.get((family, name, field_name))


def load_text_inventory(payload: Any,
                        project_sha256: str | None = None) -> TextInventory:
    """Lê o artefato de textos medidos.

    Aceita a forma que `probes/47` grava (`{"objects": [{family, name,
    texts: [{field, sha256_observed}]}]}`), porque é o artefato que já existe
    e é produzido por uma etapa read-only. Formato desconhecido vira problema,
    nunca inventário vazio silencioso — inventário vazio faria toda conferência
    "passar" por falta de dado.
    """
    inventario = TextInventory(project_sha256=project_sha256)

    if not isinstance(payload, dict):
        inventario.problems.append(
            "inventário: esperado objeto, recebido %s" % type(payload).__name__)
        return inventario

    objetos = payload.get("objects")
    if not isinstance(objetos, list):
        inventario.problems.append(
            "inventário sem lista `objects`: formato não reconhecido. Um "
            "inventário vazio faria toda conferência passar por falta de dado")
        return inventario

    for indice, objeto in enumerate(objetos):
        if not isinstance(objeto, dict):
            inventario.problems.append("objects[%d]: esperado objeto" % indice)
            continue
        familia = objeto.get("family")
        nome = objeto.get("name")
        if not isinstance(familia, str) or not isinstance(nome, str):
            inventario.problems.append(
                "objects[%d]: `family` e `name` são obrigatórios" % indice)
            continue
        for texto in objeto.get("texts") or []:
            if not isinstance(texto, dict):
                continue
            campo = texto.get("field")
            sha = texto.get("sha256_observed")
            if not isinstance(campo, str):
                continue
            if not isinstance(sha, str) or not _SHA256_RE.match(sha):
                inventario.problems.append(
                    "%s:%s:%s tem sha256 inválido: %r — documento medido sem "
                    "hash não é medição" % (familia, nome, campo, sha))
                continue
            medido = MeasuredText(family=familia, name=nome, field_name=campo,
                                  sha256=sha.lower())
            inventario.texts[medido.key] = medido

    if not inventario.texts and not inventario.problems:
        inventario.problems.append(
            "inventário não contém nenhum texto medido")
    return inventario


@dataclass
class ModificationCheck:
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


def verify_modifications(spec: Any, inventory: Any,
                         expected_project_sha256: str | None = None
                         ) -> ModificationCheck:
    """Confere cada `expected_before_sha256` da spec contra o inventário.

    Nunca levanta. Uma spec sem `modifications` passa — não há o que conferir,
    e isso é diferente de "conferi e está tudo bem": `verified` fica vazio, e
    quem lê vê a diferença.
    """
    resultado = ModificationCheck()

    if not isinstance(inventory, TextInventory) or not inventory.ok:
        motivo = (inventory.problems if isinstance(inventory, TextInventory)
                  else ["inventário inválido"])
        resultado.problems.append(
            "inventário inutilizável: " + "; ".join(motivo))
        return resultado

    if expected_project_sha256 is not None:
        if inventory.project_sha256 is None:
            resultado.problems.append(
                "inventário não declara de qual projeto foi medido, e um hash "
                "anterior só vale para o arquivo onde foi medido")
            return resultado
        if inventory.project_sha256.lower() != expected_project_sha256.lower():
            resultado.problems.append(
                "inventário é do projeto %s e a spec vai operar sobre %s"
                % (inventory.project_sha256, expected_project_sha256))
            return resultado

    if not isinstance(spec, dict):
        resultado.problems.append("spec: esperado objeto")
        return resultado

    modificacoes = spec.get("modifications", [])
    if not isinstance(modificacoes, list):
        resultado.problems.append("modifications: esperado lista")
        return resultado

    for indice, item in enumerate(modificacoes):
        rotulo = "modifications[%d]" % indice
        if not isinstance(item, dict):
            resultado.problems.append("%s: esperado objeto" % rotulo)
            continue
        familia = item.get("family")
        nome = item.get("name")
        campo = item.get("field")
        declarado = item.get("expected_before_sha256")

        medido = inventory.get(familia, nome, campo)
        if medido is None:
            resultado.problems.append(
                "%s: %s:%s:%s não está no inventário medido. Alterar o que não "
                "foi lido é escrever às cegas — e o objeto pode nem existir"
                % (rotulo, familia, nome, campo))
            continue

        if not isinstance(declarado, str) or not _SHA256_RE.match(declarado):
            resultado.problems.append(
                "%s: expected_before_sha256 ausente ou malformado; o inventário "
                "mediu %s" % (rotulo, medido.sha256))
            continue

        if declarado.lower() != medido.sha256:
            resultado.problems.append(
                "%s: a spec declara %s e o inventário mediu %s. Ou a spec foi "
                "escrita contra outro estado do projeto, ou o objeto mudou "
                "depois da medição"
                % (rotulo, declarado.lower(), medido.sha256))
            continue

        resultado.verified.append("%s:%s:%s" % (familia, nome, campo))

    return resultado


def fill_expected_before(spec: Any, inventory: Any) -> tuple[Any, list[str]]:
    """Devolve `(spec_preenchida, problemas)` com os hashes do inventário.

    Preencher é conveniência de autoria; **não substitui a conferência**. Quem
    preenche e quem aprova não devem ser a mesma etapa, e por isso esta função
    não valida nada além do necessário para preencher.
    """
    problemas: list[str] = []
    if not isinstance(spec, dict):
        return spec, ["spec: esperado objeto"]
    if not isinstance(inventory, TextInventory) or not inventory.ok:
        return spec, ["inventário inutilizável"]

    modificacoes = spec.get("modifications")
    if not isinstance(modificacoes, list):
        return spec, []

    nova = dict(spec)
    saida = []
    for item in modificacoes:
        if not isinstance(item, dict):
            saida.append(item)
            continue
        medido = inventory.get(item.get("family"), item.get("name"),
                               item.get("field"))
        if medido is None:
            problemas.append(
                "%s:%s:%s não está no inventário — nada a preencher"
                % (item.get("family"), item.get("name"), item.get("field")))
            saida.append(item)
            continue
        preenchido = dict(item)
        preenchido["expected_before_sha256"] = medido.sha256
        saida.append(preenchido)
    nova["modifications"] = saida
    return nova, problemas

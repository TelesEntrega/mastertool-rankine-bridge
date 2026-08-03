"""Carga e validação offline do **Template Profile** — o perfil congelado de
UM arquivo `.project`, com proveniência por campo (fase R0b).

Roda no lado HOST (CPython 3), é puro e não abre `.project` nenhum. Ver
`template_profile.schema.json`, no mesmo diretório, para a forma declarativa.

POR QUE ESTE MÓDULO EXISTE, TENDO `registry.py` AO LADO
=======================================================
`template_registry` amarra `application_node_path` ao `sha256` do arquivo —
uma boa defesa contra usar o caminho de índices do arquivo errado, mas ainda
uma identidade POSICIONAL. O Template Profile substitui isso por seletor
semântico (`selector.py`) e acrescenta o que faltava para a baseline ser
auditável: **proveniência por campo**.

A lacuna que motivou a proveniência é real e está registrada em
`docs/CURRENT_STATUS.md` §3: `docs/36` fechou com o template "medido e NÃO
elegível" por dois bloqueios, os dois foram resolvidos depois por medição
(`run-012`, `run-016`, `run-018`), e **nenhum documento numerado de execução
registra essa resolução**. Quem lesse só `docs/36` concluiria errado. Um
número sem origem é indistinguível de um número inventado — por isso aqui todo
campo medido precisa apontar para a run e o documento que o mediram, e a
ausência dessa ligação reprova o perfil.

O QUE ESTE MÓDULO SE RECUSA A ACEITAR COMO DECLARAÇÃO
=====================================================
Elegibilidade e maturidade são DERIVADAS, nunca lidas do arquivo. A regra é a
mesma de `registry.py`, e a razão é que um perfil que se autodeclare elegível
com bloqueio pendente é exatamente o modo de falha que a derivação impede.

A derivação tem DOIS níveis, porque os fatos do projeto exigem dois:

* `blocking_issues` — bloqueia **autoria**. Hoje: versão de compilador não
  resolvida, inventário de bibliotecas não resolvido, seletor inválido. São os
  bloqueios que impediriam uma sessão de escrita de acontecer;
* `qualification_gaps` — bloqueia **promoção de maturidade** acima de
  `field_proven`. Hoje: sem library lock, sem inventário de dispositivos, sem
  qualificação de capacidade medida (R1 não executada).

Separar os dois não é sutileza: o template está comprovadamente autorável — as
execuções W6 a W9 rodaram sobre ele com `save_as`, reabertura e build verdes —
e ao mesmo tempo não está qualificado. Um modelo de um nível só teria de
mentir em uma das duas pontas.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Any

from mastertool_bridge.templates import selector as sel

SCHEMA_VERSION = 1

_SHA256_RE = re.compile(r"^[0-9a-fA-F]{64}$")

# Escala de maturidade da fase R0 (`docs/CAPABILITY_MATRIX.md`), do menos para
# o mais qualificado. Ordenada de propósito: comparação de maturidade é por
# índice, e um nível novo entra na posição certa em vez de virar caso especial.
MATURITY_SCALE = (
    "discovered",
    "field_proven",
    "repeatable",
    "template_qualified",
    "version_qualified",
    "production_qualified",
)

# Teto que um perfil pode declarar enquanto houver lacuna de qualificação.
MATURITY_CEILING_WITH_GAPS = "field_proven"

# QUAIS lacunas bloqueiam QUAL nível.
#
# A primeira versão desta regra era grossa: qualquer lacuna de qualificação
# barrava qualquer nível acima de `field_proven`. A qualificação N=10 de
# 2026-08-02 mostrou o custo disso — dez execuções independentes, equivalentes
# e com build verde seriam recusadas como `repeatable` porque o inventário de
# dispositivos do template não foi medido. São duas perguntas diferentes:
#
#   repeatable          "isto se repete?"        → responde-se com N execuções
#   template_qualified  "isto vale NESTE template?" → precisa do template
#                                                     inteiro caracterizado
#
# Conflatá-las fazia a régua de uma cobrar a evidência da outra. O mapa abaixo
# é por nível, e o que não está listado não bloqueia. Isso NÃO afrouxa nada:
# `template_qualified` continua exigindo tudo que exigia.
GAPS_BLOCKING_BY_MATURITY = {
    "repeatable": frozenset(),
    "template_qualified": frozenset({"device_inventory_unresolved",
                                     "library_lock_unresolved"}),
    "version_qualified": frozenset({"device_inventory_unresolved",
                                    "library_lock_unresolved"}),
    "production_qualified": frozenset({"device_inventory_unresolved",
                                       "library_lock_unresolved"}),
}

# Mínimo de execuções INDEPENDENTES por nível de maturidade.
#
# O número vem do gate normativo de R1 (`docs/ROADMAP.md` §R1: "pelo menos 10
# execuções independentes"), e não de julgamento deste módulo. A primeira
# versão desta guarda exigia 2 — ela reprovava a declaração feita com uma única
# run, o que é verdade mas é o piso errado: um gate que aceita 2 quando a norma
# manda 10 deixa promover maturidade sem ter medido o que a fase exige, e o
# perfil passa a certificar menos do que promete.
#
# Os níveis acima de `repeatable` herdam o mesmo piso por MONOTONICIDADE: o
# roadmap não fixa número para eles, e um nível superior não pode exigir menos
# evidência que o nível abaixo. Quando a fase que os define fixar um número
# próprio, ele entra aqui — maior, nunca menor.
MIN_INDEPENDENT_RUNS = {
    "repeatable": 10,
    "template_qualified": 10,
    "version_qualified": 10,
    "production_qualified": 10,
}

# Bloqueios de AUTORIA (derivados).
BLOCK_COMPILER_VERSION = "compiler_version_unresolved"
BLOCK_LIBRARIES = "libraries_unresolved"
BLOCK_SELECTOR = "application_selector_invalid"

# Lacunas de QUALIFICAÇÃO (derivadas).
GAP_DEVICE_INVENTORY = "device_inventory_unresolved"
GAP_LIBRARY_LOCK = "library_lock_unresolved"
GAP_CAPABILITY_QUALIFICATION = "capability_qualification_not_measured"

_TOP_REQUIRED = frozenset({
    "schema_version", "profile_id", "product", "product_version", "project",
    "structure", "application_selector", "compiler_version", "libraries",
    "device_inventory", "library_lock", "capability_qualification",
    "provenance",
})
_TOP_OPTIONAL = frozenset({"notes"})
_TOP_ALLOWED = _TOP_REQUIRED | _TOP_OPTIONAL

_PROJECT_REQUIRED = frozenset({"file_name", "sha256", "size_bytes", "classification"})
_STRUCTURE_REQUIRED = frozenset({"root_count", "node_count", "tree_sha256",
                                 "tree_sha256_scope"})
_STRUCTURE_OPTIONAL = frozenset({"unclassified_node_count"})
_EVIDENCE_REQUIRED = frozenset({"status", "value", "source"})
_EVIDENCE_OPTIONAL = frozenset({"reason"})
_PROVENANCE_REQUIRED = frozenset({"field", "run", "document"})
_PROVENANCE_OPTIONAL = frozenset({"commit"})
_CAPQUAL_REQUIRED = frozenset({"status", "runs", "reason"})
_CAPQUAL_OPTIONAL = frozenset({"capabilities"})
_CAPABILITY_REQUIRED = frozenset({"operation", "maturity", "runs", "document"})

# Campos cuja medição EXIGE entrada de proveniência. Um número estrutural sem
# origem é o problema que este módulo existe para tornar impossível.
PROVENANCE_REQUIRED_FIELDS = (
    "project.sha256",
    "structure.node_count",
    "structure.tree_sha256",
    "application_selector",
)


@dataclass(frozen=True)
class Evidence:
    status: str
    value: Any
    source: str
    reason: str | None = None

    @property
    def is_measured(self) -> bool:
        return self.status == "measured"


@dataclass(frozen=True)
class ProjectIdentity:
    file_name: str
    sha256: str
    size_bytes: int
    classification: str


@dataclass(frozen=True)
class Structure:
    root_count: int
    node_count: int
    tree_sha256: str
    tree_sha256_scope: str
    unclassified_node_count: int | None = None


@dataclass(frozen=True)
class QualifiedCapability:
    operation: str
    maturity: str
    runs: tuple[str, ...]
    document: str


@dataclass(frozen=True)
class ProvenanceEntry:
    field_path: str
    run: str
    document: str
    commit: str | None = None


@dataclass(frozen=True)
class TemplateProfile:
    profile_id: str
    product: str
    product_version: str
    project: ProjectIdentity
    structure: Structure
    application_selector: sel.SemanticSelector
    compiler_version: Evidence
    libraries: Evidence
    device_inventory: Evidence
    library_lock: Evidence
    provenance: tuple[ProvenanceEntry, ...]
    notes: tuple[str, ...] = ()
    # --- derivados: nunca lidos do arquivo -----------------------------------
    blocking_issues: tuple[str, ...] = ()
    qualification_gaps: tuple[str, ...] = ()
    qualified_capabilities: tuple[QualifiedCapability, ...] = ()

    @property
    def authoring_eligible(self) -> bool:
        return not self.blocking_issues

    @property
    def qualified(self) -> bool:
        """Qualificado é OUTRA coisa de elegível para autoria. O template
        atual é o exemplo vivo: autorável (W6–W9 rodaram) e não qualificado
        (R1 não foi executada)."""
        return not self.qualification_gaps


@dataclass(frozen=True)
class ProfileValidationResult:
    problems: list[str] = field(default_factory=list)
    profiles_by_sha256: dict[str, TemplateProfile] = field(default_factory=dict)

    @property
    def ok(self) -> bool:
        return not self.problems


# --- validação de partes ------------------------------------------------------

def _validate_evidence(label: str, obj: Any, problems: list[str]) -> Evidence | None:
    if not isinstance(obj, dict):
        problems.append("%s: esperado objeto, recebido %s"
                        % (label, type(obj).__name__))
        return None
    desconhecidos = sorted(set(obj) - (_EVIDENCE_REQUIRED | _EVIDENCE_OPTIONAL))
    if desconhecidos:
        problems.append("%s: campo(s) desconhecido(s): %s"
                        % (label, ", ".join(desconhecidos)))
    faltando = sorted(_EVIDENCE_REQUIRED - set(obj))
    if faltando:
        problems.append("%s: campo(s) obrigatório(s) ausente(s): %s"
                        % (label, ", ".join(faltando)))
        return None

    status = obj.get("status")
    if status not in ("measured", "unresolved"):
        problems.append("%s.status: esperado 'measured' ou 'unresolved', "
                        "recebido %r" % (label, status))
        return None

    source = obj.get("source")
    if not isinstance(source, str) or not source.strip():
        problems.append("%s.source: string não vazia obrigatória nos dois "
                        "status — de onde veio (ou não veio) a evidência"
                        % label)

    valor = obj.get("value")
    razao = obj.get("reason")

    if status == "measured":
        if valor is None:
            problems.append("%s.value: 'measured' com valor nulo é "
                            "contradição — medir produz valor" % label)
        if isinstance(valor, str) and not valor.strip():
            problems.append("%s.value: string vazia não é medição" % label)
        if razao is not None:
            problems.append("%s.reason: só existe quando 'unresolved' — "
                            "medição não tem por que se justificar" % label)
    else:
        if valor is not None:
            problems.append("%s.value: 'unresolved' exige `null`, nunca um "
                            "valor de consolação" % label)
        if not isinstance(razao, str) or not razao.strip():
            problems.append("%s.reason: obrigatório quando 'unresolved' — "
                            "lacuna sem motivo é lacuna escondida" % label)

    # Devolve o objeto mesmo com problemas registrados, para que as checagens
    # seguintes rodem e o operador veja tudo de uma vez; quem decide abortar é
    # `validate_template_profile`, pelo `problems`.
    return Evidence(status=status, value=valor,
                    source=source if isinstance(source, str) else "",
                    reason=razao if isinstance(razao, str) else None)


def _validate_project(obj: Any, problems: list[str]) -> ProjectIdentity | None:
    if not isinstance(obj, dict):
        problems.append("project: esperado objeto")
        return None
    desconhecidos = sorted(set(obj) - _PROJECT_REQUIRED)
    if desconhecidos:
        problems.append("project: campo(s) desconhecido(s): %s"
                        % ", ".join(desconhecidos))
    faltando = sorted(_PROJECT_REQUIRED - set(obj))
    if faltando:
        problems.append("project: campo(s) obrigatório(s) ausente(s): %s"
                        % ", ".join(faltando))
        return None

    sha = obj.get("sha256")
    if not isinstance(sha, str) or not _SHA256_RE.match(sha):
        problems.append("project.sha256: esperado hex de 64 caracteres")
        return None
    tamanho = obj.get("size_bytes")
    if isinstance(tamanho, bool) or not isinstance(tamanho, int) or tamanho < 1:
        problems.append("project.size_bytes: esperado inteiro >= 1")
        return None
    for campo in ("file_name", "classification"):
        if not isinstance(obj.get(campo), str) or not obj[campo].strip():
            problems.append("project.%s: string não vazia obrigatória" % campo)
            return None
    return ProjectIdentity(file_name=obj["file_name"], sha256=sha,
                           size_bytes=tamanho,
                           classification=obj["classification"])


def _validate_structure(obj: Any, problems: list[str]) -> Structure | None:
    if not isinstance(obj, dict):
        problems.append("structure: esperado objeto")
        return None
    desconhecidos = sorted(set(obj) - (_STRUCTURE_REQUIRED | _STRUCTURE_OPTIONAL))
    if desconhecidos:
        problems.append("structure: campo(s) desconhecido(s): %s"
                        % ", ".join(desconhecidos))
    faltando = sorted(_STRUCTURE_REQUIRED - set(obj))
    if faltando:
        problems.append("structure: campo(s) obrigatório(s) ausente(s): %s"
                        % ", ".join(faltando))
        return None

    for campo in ("root_count", "node_count"):
        valor = obj.get(campo)
        if isinstance(valor, bool) or not isinstance(valor, int) or valor < 1:
            problems.append("structure.%s: esperado inteiro >= 1" % campo)
            return None
    tree = obj.get("tree_sha256")
    if not isinstance(tree, str) or not _SHA256_RE.match(tree):
        problems.append("structure.tree_sha256: esperado hex de 64 caracteres")
        return None
    escopo = obj.get("tree_sha256_scope")
    if not isinstance(escopo, str) or not escopo.strip():
        problems.append(
            "structure.tree_sha256_scope: obrigatório — o mesmo nome de campo "
            "já designou escopos diferentes nesta base (um nível de filhos no "
            "registry de W1.3B; árvore inteira em docs/36), e comparar os dois "
            "como se fossem a mesma coisa é comparar o incomparável")
        return None
    nao_classificados = obj.get("unclassified_node_count")
    if nao_classificados is not None:
        if isinstance(nao_classificados, bool) \
                or not isinstance(nao_classificados, int) \
                or nao_classificados < 0:
            problems.append("structure.unclassified_node_count: esperado "
                            "inteiro >= 0 ou ausente")
            return None
        if nao_classificados > obj["node_count"]:
            problems.append("structure.unclassified_node_count: %d não "
                            "classificados em %d nós é aritmética impossível"
                            % (nao_classificados, obj["node_count"]))
            return None
    return Structure(root_count=obj["root_count"], node_count=obj["node_count"],
                     tree_sha256=tree, tree_sha256_scope=escopo,
                     unclassified_node_count=nao_classificados)


def _validate_provenance(obj: Any, problems: list[str]) -> tuple[ProvenanceEntry, ...]:
    if not isinstance(obj, list) or not obj:
        problems.append("provenance: esperado lista não vazia — perfil sem "
                        "origem é perfil sem evidência")
        return ()
    entradas: list[ProvenanceEntry] = []
    for indice, item in enumerate(obj):
        rotulo = "provenance[%d]" % indice
        if not isinstance(item, dict):
            problems.append("%s: esperado objeto" % rotulo)
            continue
        desconhecidos = sorted(set(item) - (_PROVENANCE_REQUIRED | _PROVENANCE_OPTIONAL))
        if desconhecidos:
            problems.append("%s: campo(s) desconhecido(s): %s"
                            % (rotulo, ", ".join(desconhecidos)))
        faltando = sorted(_PROVENANCE_REQUIRED - set(item))
        if faltando:
            problems.append("%s: campo(s) obrigatório(s) ausente(s): %s"
                            % (rotulo, ", ".join(faltando)))
            continue
        ruim = [c for c in ("field", "run", "document")
                if not isinstance(item.get(c), str) or not item[c].strip()]
        if ruim:
            problems.append("%s: campo(s) com string vazia: %s"
                            % (rotulo, ", ".join(ruim)))
            continue
        commit = item.get("commit")
        if commit is not None and (not isinstance(commit, str) or not commit.strip()):
            problems.append("%s.commit: string não vazia ou ausente" % rotulo)
            continue
        entradas.append(ProvenanceEntry(field_path=item["field"], run=item["run"],
                                        document=item["document"], commit=commit))
    return tuple(entradas)


def _validate_capability_qualification(
        obj: Any, lacunas_abertas: Any,
        problems: list[str]) -> tuple[str, tuple[QualifiedCapability, ...]]:
    """Devolve `(status, capacidades_derivadas)`.

    A regra central: **um perfil não promove maturidade**. Enquanto o status é
    `not_measured`, a lista derivada é vazia — e uma lista declarada não vazia
    reprova, em vez de ser aceita como declaração.
    """
    if not isinstance(obj, dict):
        problems.append("capability_qualification: esperado objeto")
        return "not_measured", ()
    desconhecidos = sorted(set(obj) - (_CAPQUAL_REQUIRED | _CAPQUAL_OPTIONAL))
    if desconhecidos:
        problems.append("capability_qualification: campo(s) desconhecido(s): %s"
                        % ", ".join(desconhecidos))
    faltando = sorted(_CAPQUAL_REQUIRED - set(obj))
    if faltando:
        problems.append("capability_qualification: campo(s) obrigatório(s) "
                        "ausente(s): %s" % ", ".join(faltando))
        return "not_measured", ()

    status = obj.get("status")
    if status not in ("not_measured", "measured"):
        problems.append("capability_qualification.status: esperado "
                        "'not_measured' ou 'measured', recebido %r" % (status,))
        return "not_measured", ()

    runs = obj.get("runs")
    if not isinstance(runs, list) or any(
            not isinstance(r, str) or not r.strip() for r in runs):
        problems.append("capability_qualification.runs: esperado lista de "
                        "strings não vazias")
        return status, ()

    declaradas = obj.get("capabilities", [])
    if not isinstance(declaradas, list):
        problems.append("capability_qualification.capabilities: esperado lista")
        return status, ()

    if status == "not_measured":
        if runs:
            problems.append("capability_qualification: 'not_measured' com "
                            "%d run(s) declarada(s) é contradição — ou a "
                            "medição aconteceu, ou não" % len(runs))
        if declaradas:
            problems.append(
                "capability_qualification: %d capacidade(s) declarada(s) com "
                "status 'not_measured'. Um perfil não promove maturidade: "
                "medição promove" % len(declaradas))
        razao = obj.get("reason")
        if not isinstance(razao, str) or not razao.strip():
            problems.append("capability_qualification.reason: obrigatório "
                            "quando 'not_measured'")
        return status, ()

    # status == "measured"
    if not runs:
        problems.append("capability_qualification: 'measured' sem nenhuma run "
                        "é medição sem execução")
    capacidades: list[QualifiedCapability] = []
    teto = MATURITY_SCALE.index(MATURITY_CEILING_WITH_GAPS)
    for indice, item in enumerate(declaradas):
        rotulo = "capability_qualification.capabilities[%d]" % indice
        if not isinstance(item, dict):
            problems.append("%s: esperado objeto" % rotulo)
            continue
        desconhecidos = sorted(set(item) - _CAPABILITY_REQUIRED)
        if desconhecidos:
            problems.append("%s: campo(s) desconhecido(s): %s"
                            % (rotulo, ", ".join(desconhecidos)))
        faltando = sorted(_CAPABILITY_REQUIRED - set(item))
        if faltando:
            problems.append("%s: campo(s) obrigatório(s) ausente(s): %s"
                            % (rotulo, ", ".join(faltando)))
            continue
        maturidade = item.get("maturity")
        if maturidade not in MATURITY_SCALE:
            problems.append("%s.maturity: fora da escala: %r"
                            % (rotulo, maturidade))
            continue
        item_runs = item.get("runs")
        if not isinstance(item_runs, list) or not item_runs or any(
                not isinstance(r, str) or not r.strip() for r in item_runs):
            problems.append("%s.runs: lista não vazia de strings" % rotulo)
            continue
        nivel = MATURITY_SCALE.index(maturidade)
        # Bloqueio POR NÍVEL: só as lacunas que aquele nível de fato exige.
        # Ver `GAPS_BLOCKING_BY_MATURITY` para por que a regra deixou de ser
        # "qualquer lacuna barra qualquer promoção".
        bloqueadoras = GAPS_BLOCKING_BY_MATURITY.get(maturidade, frozenset())
        impeditivas = sorted(set(lacunas_abertas) & bloqueadoras)
        if nivel > teto and impeditivas:
            problems.append(
                "%s: maturidade %r exige que estas lacunas do perfil estejam "
                "fechadas, e elas não estão: %s"
                % (rotulo, maturidade, ", ".join(impeditivas)))
            continue
        minimo = MIN_INDEPENDENT_RUNS.get(maturidade)
        if minimo is not None and len(set(item_runs)) < minimo:
            problems.append(
                "%s: %r declarada com %d run(s) distinta(s); o gate normativo "
                "da R1 exige %d execuções independentes. Repetir a mesma run "
                "não a torna repetível, e um piso menor que o da norma faria "
                "este perfil certificar menos do que promete"
                % (rotulo, maturidade, len(set(item_runs)), minimo))
            continue
        for campo in ("operation", "document"):
            if not isinstance(item.get(campo), str) or not item[campo].strip():
                problems.append("%s.%s: string não vazia" % (rotulo, campo))
                break
        else:
            capacidades.append(QualifiedCapability(
                operation=item["operation"], maturity=maturidade,
                runs=tuple(item_runs), document=item["document"]))
    return status, tuple(capacidades)


def _check_provenance_coverage(provenance: tuple[ProvenanceEntry, ...],
                               medidos: tuple[str, ...],
                               problems: list[str]) -> None:
    """Confere que todo campo que precisa de origem tem uma.

    `medidos` são as evidências com status `measured` — elas entram na
    exigência dinamicamente, e não por lista fixa, porque é justamente o campo
    MEDIDO que precisa dizer quem o mediu. Uma evidência não resolvida não
    entra: ela já carrega `reason`, que é a sua própria origem.
    """
    cobertos = {p.field_path for p in provenance}
    for campo in tuple(PROVENANCE_REQUIRED_FIELDS) + medidos:
        if campo in cobertos:
            continue
        # Cobertura por prefixo: uma entrada para `structure` cobre
        # `structure.node_count`. Explícito é melhor, mas exigir entrada por
        # folha transformaria proveniência em burocracia.
        prefixo = campo.split(".", 1)[0]
        if prefixo in cobertos:
            continue
        problems.append(
            "provenance: nenhuma entrada cobre %r — número medido sem origem "
            "é indistinguível de número inventado, que é a lacuna que este "
            "perfil existe para fechar" % campo)


# --- validação do perfil inteiro ---------------------------------------------

def validate_template_profile(data: Any) -> ProfileValidationResult:
    """Valida um perfil (ou uma lista deles) e DERIVA elegibilidade.

    Nunca levanta: entrada degenerada vira `problems`. Quem decide interromper
    um fluxo é o chamador.
    """
    problems: list[str] = []
    if not isinstance(data, dict):
        return ProfileValidationResult(
            problems=["perfil: esperado objeto, recebido %s"
                      % type(data).__name__])

    desconhecidos = sorted(set(data) - _TOP_ALLOWED)
    if desconhecidos:
        problems.append("perfil: campo(s) desconhecido(s): %s"
                        % ", ".join(desconhecidos))
    faltando = sorted(_TOP_REQUIRED - set(data))
    if faltando:
        problems.append("perfil: campo(s) obrigatório(s) ausente(s): %s"
                        % ", ".join(faltando))
        return ProfileValidationResult(problems=problems)

    versao = data.get("schema_version")
    if versao != SCHEMA_VERSION:
        problems.append("schema_version: esperado %d, recebido %r"
                        % (SCHEMA_VERSION, versao))

    for campo in ("profile_id", "product", "product_version"):
        if not isinstance(data.get(campo), str) or not data[campo].strip():
            problems.append("%s: string não vazia obrigatória" % campo)

    projeto = _validate_project(data.get("project"), problems)
    estrutura = _validate_structure(data.get("structure"), problems)

    seletor, problemas_seletor = sel.parse_selector(data.get("application_selector"))
    for problema in problemas_seletor:
        problems.append("application_selector -> %s" % problema)

    compilador = _validate_evidence("compiler_version",
                                    data.get("compiler_version"), problems)
    bibliotecas = _validate_evidence("libraries", data.get("libraries"), problems)
    dispositivos = _validate_evidence("device_inventory",
                                      data.get("device_inventory"), problems)
    trava = _validate_evidence("library_lock", data.get("library_lock"), problems)

    provenance = _validate_provenance(data.get("provenance"), problems)
    medidos = tuple(
        nome for nome, evidencia in (("compiler_version", compilador),
                                     ("libraries", bibliotecas),
                                     ("device_inventory", dispositivos),
                                     ("library_lock", trava))
        if evidencia is not None and evidencia.is_measured)
    _check_provenance_coverage(provenance, medidos, problems)

    notas_brutas = data.get("notes", [])
    notas: tuple[str, ...] = ()
    if not isinstance(notas_brutas, list) or any(
            not isinstance(n, str) or not n.strip() for n in notas_brutas):
        problems.append("notes: esperado lista de strings não vazias")
    else:
        notas = tuple(notas_brutas)

    # --- DERIVAÇÃO ----------------------------------------------------------
    bloqueios: list[str] = []
    if compilador is None or not compilador.is_measured:
        bloqueios.append(BLOCK_COMPILER_VERSION)
    if bibliotecas is None or not bibliotecas.is_measured:
        bloqueios.append(BLOCK_LIBRARIES)
    if seletor is None:
        bloqueios.append(BLOCK_SELECTOR)

    lacunas: list[str] = []
    if dispositivos is None or not dispositivos.is_measured:
        lacunas.append(GAP_DEVICE_INVENTORY)
    if trava is None or not trava.is_measured:
        lacunas.append(GAP_LIBRARY_LOCK)

    status_qual, capacidades = _validate_capability_qualification(
        data.get("capability_qualification"), list(lacunas), problems)
    if status_qual != "measured":
        lacunas.append(GAP_CAPABILITY_QUALIFICATION)

    if problems:
        return ProfileValidationResult(problems=problems)

    perfil = TemplateProfile(
        profile_id=data["profile_id"], product=data["product"],
        product_version=data["product_version"], project=projeto,
        structure=estrutura, application_selector=seletor,
        compiler_version=compilador, libraries=bibliotecas,
        device_inventory=dispositivos, library_lock=trava,
        provenance=provenance, notes=notas,
        blocking_issues=tuple(bloqueios), qualification_gaps=tuple(lacunas),
        qualified_capabilities=capacidades)

    return ProfileValidationResult(problems=[],
                                   profiles_by_sha256={projeto.sha256: perfil})


def load_template_profile(text: str) -> ProfileValidationResult:
    """Mesma validação, a partir do texto JSON. JSON malformado vira
    `problems`, não exceção — quem carrega um perfil não deveria precisar
    saber a diferença entre "arquivo corrompido" e "perfil inválido" para
    tratar as duas como recusa."""
    try:
        data = json.loads(text)
    except (ValueError, TypeError) as exc:
        return ProfileValidationResult(problems=["JSON inválido: %s" % exc])
    return validate_template_profile(data)


def select_profile_for_file(result: ProfileValidationResult,
                            file_sha256: str) -> TemplateProfile | None:
    """Única forma de obter um perfil a partir de um arquivo real: pelo sha256
    REALMENTE computado do arquivo em mãos.

    Não existe atalho por `profile_id` — pela mesma razão que
    `registry.resolve_node_path_for_file` não o oferece: dois perfis do "mesmo"
    template com arquivos diferentes descrevem árvores diferentes, e pedir pelo
    nome devolveria a descrição do arquivo errado.
    """
    if not result.ok:
        return None
    if not isinstance(file_sha256, str) or not _SHA256_RE.match(file_sha256):
        return None
    return result.profiles_by_sha256.get(file_sha256)


def authoring_refusal_reason(result: ProfileValidationResult,
                             file_sha256: str) -> str | None:
    """Por que a autoria seria recusada, em texto. `None` quando não há
    recusa. Recusa silenciosa é indistinguível de perfil ausente, e as duas
    pedem ações opostas."""
    if not result.ok:
        return "perfil inválido: %d problema(s)" % len(result.problems)
    perfil = select_profile_for_file(result, file_sha256)
    if perfil is None:
        return "nenhum perfil descreve o arquivo %s" % file_sha256
    if not perfil.authoring_eligible:
        return ("perfil %r não é elegível para autoria; bloqueios: %s"
                % (perfil.profile_id, ", ".join(perfil.blocking_issues)))
    return None

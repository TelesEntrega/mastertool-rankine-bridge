"""R9.3 — as sequências do descritivo como requisitos rastreáveis.

O QUE ESTE MÓDULO EXTRAI, E O QUE ELE SE RECUSA A EXTRAIR
=========================================================
Ele extrai o que o documento SUSTENTA mecanicamente:

* as sequências, pelos títulos;
* as tabelas de estado/passo que pertencem a cada uma, por posição;
* as TAGs citadas, conferidas contra o inventário de R9.2;
* as pendências, promovidas a lacunas de primeira classe;
* frases que atravessam fronteira de dono, detectadas por verbo.

Ele **não** extrai passo, condição de entrada, condição de conclusão ou
comportamento em falha a partir de prosa livre. Um extrator que fizesse isso
por regra de frase produziria uma máquina de estados plausível e não medida —
e a diferença entre as duas só apareceria em campo.

O QUE TORNOU A EXTRAÇÃO POSSÍVEL
================================
Medido no corpus: 61 das 65 TAGs do inventário aparecem citadas no corpo, e o
documento traz nove tabelas de duas colunas com cabeçalho explícito
(`Estado | Ação`, `Passo | Ação`, `Condição | Regra confirmada`). Essas
tabelas SÃO as máquinas de estado.

Sem isso, R9.3 seria adivinhação. Com isso, ele é leitura.

PAPEL VEM DA COLUNA, E SÓ GROSSO
================================
O cabeçalho da tabela diz a natureza da célula — `Condição` de um lado,
`Ação` do outro. Isso é evidência do documento, e vira papel `derived` com
regra nomeada.

O que **não** se deriva é o papel fino: se uma TAG na coluna de ação é
comando, realimentação ou disparo. Uma frase de ação cita sensores como
condição o tempo todo. Papel fino fica `requires_human_structuring`.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from mastertool_bridge.plant.model import Fact, Gap, Origin

SCHEMA_VERSION = 1
MODEL_KIND = "process_requirements"

# Papéis FECHADOS. Os dois primeiros são deriváveis da coluna; os demais
# exigem estruturação humana e existem aqui para que ela tenha onde pousar.
ROLES = (
    "condition_context",        # citada em célula cuja coluna é condição/estado
    "action_context",           # citada em célula cuja coluna é ação
    "trigger",
    "condition",
    "command",
    "feedback",
    "completion",
    "fault",
    "parameter",
    "safety_reference",
    "handshake_reference",
)

# Papéis que este módulo pode atribuir sozinho. O resto fica em aberto.
DERIVABLE_ROLES = frozenset({"condition_context", "action_context"})

RULE_COLUMN = "column_header_semantics"

# Cabeçalhos observados no corpus, e o que cada coluna significa. Mapa
# LITERAL: um cabeçalho novo não é classificado por semelhança — ele vira
# diagnóstico, e alguém decide.
COLUMN_KIND = {
    "ESTADO": "condition",
    "PASSO": "condition",
    "CONDICAO": "condition",
    "ESTADODELOCALIZACAO": "condition",
    "ACAO": "action",
    "ACAOCONDICAO": "action",
    "REGRACONFIRMADA": "action",
    "SIGNIFICADOCONDICAO": "action",
    "FINALIDADE": "action",
}

# Verbos que indicam interação atravessando fronteira de dono. Detectam a
# EXISTÊNCIA da interação; nunca o protocolo.
CROSS_OWNER_VERBS = (
    "libera", "liberar", "autoriza", "autorizar", "solicita", "solicitar",
    "informa", "informar", "aguarda", "aguardar", "sinaliza", "sinalizar",
    "handshake", "confirma recebimento", "entrega", "recebe do", "envia para",
)

# Termos que marcam referência de segurança no texto. Marcam REFERÊNCIA, e
# nunca classificação — a política é a mesma de R9.2.
SAFETY_TERMS = (
    "emergenc", "barreira", "safety", "cortina", "intertrav", "nr-12", "nr12",
    "parada segura", "rele de seguranca", "scanner",
)


def _sem_acento(t: str) -> str:
    tabela = str.maketrans("ÁÀÂÃÄÉÈÊËÍÌÎÏÓÒÔÕÖÚÙÛÜÇáàâãäéèêëíìîïóòôõöúùûüç",
                           "AAAAAEEEEIIIIOOOOOUUUUCaaaaaeeeeiiiiooooouuuuc")
    return t.translate(tabela)


def _chave(t: str) -> str:
    return re.sub(r"[^A-Z]", "", _sem_acento(t or "").upper())


@dataclass(frozen=True)
class PointReference:
    """Uma TAG citada dentro de uma sequência."""

    tag: str
    role: Fact
    known_in_inventory: bool
    origin: Origin
    excerpt: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "tag": self.tag,
            "role": self.role.to_dict(),
            "known_in_inventory": self.known_in_inventory,
            "origin": self.origin.to_dict(),
            "excerpt": self.excerpt,
        }


@dataclass(frozen=True)
class StateRow:
    """Uma linha de tabela de estado/passo — a unidade estruturada do
    documento."""

    left: str
    right: str
    left_kind: str
    right_kind: str
    origin: Origin

    def to_dict(self) -> dict[str, Any]:
        return {"left": self.left, "right": self.right,
                "left_kind": self.left_kind, "right_kind": self.right_kind,
                "origin": self.origin.to_dict()}


@dataclass
class Sequence:
    sequence_id: str
    name: str
    origin: Origin
    state_rows: list = field(default_factory=list)
    point_refs: list = field(default_factory=list)
    cross_owner: list = field(default_factory=list)
    safety_refs: list = field(default_factory=list)
    unresolved: list = field(default_factory=list)
    diagnostics: list = field(default_factory=list)

    @property
    def structured(self) -> bool:
        """Tem tabela de estado? Sem ela, o comportamento só existe em prosa,
        e este módulo não o extrai."""
        return bool(self.state_rows)

    def to_dict(self) -> dict[str, Any]:
        return {
            "sequence_id": self.sequence_id,
            "name": self.name,
            "origin": self.origin.to_dict(),
            "structured": self.structured,
            "state_rows": [r.to_dict() for r in self.state_rows],
            "point_refs": [p.to_dict() for p in sorted(
                self.point_refs, key=lambda p: (p.tag, p.origin.locator))],
            "cross_owner_interactions": list(self.cross_owner),
            "safety_references": sorted(self.safety_refs),
            "unresolved": list(self.unresolved),
            "diagnostics": list(self.diagnostics),
            # NUNCA extraídos deste documento por regra de frase. Ficam
            # nomeados para que a estruturação humana tenha onde pousar.
            "requires_human_structuring": [
                "start_conditions", "steps", "completion_conditions",
                "abort_conditions", "fault_conditions", "timeouts",
            ],
        }


@dataclass
class ProcessRequirements:
    project: str
    source_version: str | None = None
    sequences: list = field(default_factory=list)
    gaps: list = field(default_factory=list)
    diagnostics: list = field(default_factory=list)
    uncited_points: list = field(default_factory=list)

    def matrix(self) -> list:
        """Sequência × equipamento × ponto × papel, achatada."""
        linhas = []
        for s in self.sequences:
            for r in s.point_refs:
                linhas.append({
                    "sequence_id": s.sequence_id,
                    "sequence": s.name,
                    "tag": r.tag,
                    "role": r.role.value,
                    "role_state": r.role.state,
                    "known_in_inventory": r.known_in_inventory,
                    "locator": r.origin.locator,
                })
        return sorted(linhas, key=lambda x: (x["sequence_id"], x["tag"],
                                             x["locator"] or ""))

    def summary(self) -> dict[str, Any]:
        # `role` é `None` quando a coluna de origem tem cabeçalho fora do
        # mapa — papel indeterminado é um resultado, não um erro. A chave
        # vira texto para que a contagem não dependa de ordenar `None`.
        papeis: dict = {}
        for l in self.matrix():
            chave = l["role"] or "indeterminate"
            papeis[chave] = papeis.get(chave, 0) + 1
        return {
            "sequences": len(self.sequences),
            "structured_sequences": sum(1 for s in self.sequences if s.structured),
            "state_rows": sum(len(s.state_rows) for s in self.sequences),
            "point_references": len(self.matrix()),
            "roles": dict(sorted(papeis.items())),
            "cross_owner_interactions": sum(len(s.cross_owner)
                                            for s in self.sequences),
            "safety_references": sum(len(s.safety_refs) for s in self.sequences),
            "uncited_inventory_points": len(self.uncited_points),
            "gaps": len(self.gaps),
            "blocking_gaps": sum(1 for g in self.gaps if g.blocks_generation),
        }

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": SCHEMA_VERSION,
            "model_kind": MODEL_KIND,
            "project": self.project,
            "source_version": self.source_version,
            "sequences": [s.to_dict() for s in
                          sorted(self.sequences, key=lambda s: s.sequence_id)],
            "matrix": self.matrix(),
            "uncited_inventory_points": sorted(self.uncited_points),
            "gaps": [g.to_dict() for g in
                     sorted(self.gaps, key=lambda g: (g.kind, g.subject))],
            "diagnostics": sorted(self.diagnostics,
                                  key=lambda d: (d.get("code", ""),
                                                 d.get("subject", ""))),
            "summary": self.summary(),
        }


# =============================================================================
# ingestão
# =============================================================================

def _origem(doc, versao, locator) -> Origin:
    return Origin(document=doc, locator=locator, version=versao)


def _tags_em(texto: str, conhecidas) -> list:
    """TAGs citadas, por limite de palavra.

    Sem `\\b`, `MTI1` casaria dentro de `MTI10`. O inventário real tem
    famílias numeradas, e essa colisão produziria referência silenciosamente
    errada.
    """
    achadas = []
    for tag in conhecidas:
        if re.search(r"\b%s\b" % re.escape(tag), texto):
            achadas.append(tag)
    return sorted(achadas)


def _papel_da_coluna(kind: str, doc, versao, locator) -> Fact:
    if kind == "condition":
        return Fact(value="condition_context", state="derived",
                    rule=RULE_COLUMN,
                    note="citada em coluna cujo cabeçalho é de condição/estado")
    if kind == "action":
        return Fact(value="action_context", state="derived", rule=RULE_COLUMN,
                    note="citada em coluna cujo cabeçalho é de ação")
    return Fact(value=None, state="absent",
                note="coluna de cabeçalho não reconhecido: papel indeterminado")


def ingest_sequences(*, headings, tables, paragraphs, pendencies,
                     inventory_tags, document: str,
                     version: str | None = None,
                     project: str = "planta") -> ProcessRequirements:
    """Constrói os requisitos a partir da estrutura já extraída do documento.

    Recebe estrutura, não arquivo: o adaptador `.docx` mora em outro lugar,
    pelo mesmo motivo de R9.2 — a semântica fica testável com fixture
    sintética e dado de cliente não entra no repositório.

    `headings`   [(nivel, texto, locator)]
    `tables`     [{"header": (esq, dir), "rows": [(esq, dir)], "after_heading": idx}]
    `paragraphs` [(texto, locator, after_heading_idx)]
    """
    req = ProcessRequirements(project=project, source_version=version)
    conhecidas = set(inventory_tags)
    citadas: set = set()

    subtitulos = [(i, h) for i, h in enumerate(headings) if h[0] == 2]
    if not subtitulos:
        req.gaps.append(Gap(
            kind="no_sequences_found", subject=document,
            detail="nenhum subtítulo de sequência localizado",
            origin=_origem(document, version, "?")))
        return req

    for ordem, (indice, (_, nome, locator)) in enumerate(subtitulos, start=1):
        seq = Sequence(sequence_id="SEQ-%03d" % ordem, name=nome,
                       origin=_origem(document, version, locator))

        def registrar(texto, loc, kind):
            for tag in _tags_em(texto, conhecidas):
                citadas.add(tag)
                seq.point_refs.append(PointReference(
                    tag=tag, role=_papel_da_coluna(kind, document, version, loc),
                    known_in_inventory=True,
                    origin=_origem(document, version, loc),
                    excerpt=texto[:120]))
            baixo = _sem_acento(texto).lower()
            if any(v in baixo for v in CROSS_OWNER_VERBS):
                seq.cross_owner.append({
                    "excerpt": texto[:160],
                    "locator": loc,
                    "producer": None,
                    "consumer": None,
                    "handshake_contract": "required",
                    "note": ("interação atravessando fronteira de dono "
                             "detectada pelo verbo; o protocolo NÃO é "
                             "inferido"),
                })
            if any(t in baixo for t in SAFETY_TERMS):
                seq.safety_refs.append(loc)

        for tabela in tables:
            if tabela.get("after_heading") != indice:
                continue
            cab_esq, cab_dir = tabela["header"]
            k_esq = COLUMN_KIND.get(_chave(cab_esq))
            k_dir = COLUMN_KIND.get(_chave(cab_dir))
            for nao_reconhecido, texto in (("esquerda", cab_esq),
                                           ("direita", cab_dir)):
                if COLUMN_KIND.get(_chave(texto)) is None:
                    seq.diagnostics.append({
                        "code": "unknown_column_header",
                        "subject": texto,
                        "message": ("cabeçalho %r não está no mapa; a coluna "
                                    "%s não classifica papel" %
                                    (texto, nao_reconhecido))})
            for numero, (esq, dir_) in enumerate(tabela["rows"], start=1):
                loc = "%s/tab/L%d" % (locator, numero)
                seq.state_rows.append(StateRow(
                    left=esq, right=dir_,
                    left_kind=k_esq or "unknown",
                    right_kind=k_dir or "unknown",
                    origin=_origem(document, version, loc)))
                registrar(esq, loc + "/esq", k_esq)
                registrar(dir_, loc + "/dir", k_dir)

        for texto, loc, pertence in paragraphs:
            if pertence == indice:
                registrar(texto, loc, None)

        if not seq.structured:
            seq.unresolved.append({
                "kind": "behaviour_only_in_prose",
                "detail": ("a sequência não tem tabela de estado; passos e "
                           "condições existem apenas em prosa e não são "
                           "extraídos por regra de frase"),
            })
        req.sequences.append(seq)

    # PONTOS DO INVENTÁRIO SEM COMPORTAMENTO DESCRITO EM SEQUÊNCIA.
    #
    # A afirmação é precisa de propósito: "não citado em nenhuma sequência"
    # NÃO é "não citado no documento". Uma TAG pode aparecer numa seção de
    # nível 1 — inventário de sensores, por exemplo — sem que exista lógica
    # descrita para ela. Dizer "não citado" seria mais forte do que o medido,
    # e mandaria alguém procurar uma omissão que talvez não exista.
    req.uncited_points = sorted(conhecidas - citadas)
    if req.uncited_points:
        req.gaps.append(Gap(
            kind="point_without_sequence_behaviour",
            subject="descritivo",
            detail=("%d ponto(s) do inventário não aparecem em nenhuma "
                    "sequência: %s. Eles podem estar citados fora das "
                    "sequências; o que falta é comportamento descrito"
                    % (len(req.uncited_points), ", ".join(req.uncited_points))),
            origin=_origem(document, version, "corpo"),
            blocks_generation=False))

    req.gaps.extend(_pendencias_como_lacunas(pendencies, document, version))
    return req


# Estados de pendência. `pending` sozinho não serve: a CAUSA muda a ação.
PENDENCY_STATES = ("open", "human_decision_required", "source_missing",
                   "conflicting_sources", "resolved")


def _pendencias_como_lacunas(pendencies, documento, versao) -> list:
    """As pendências do próprio documento viram lacunas de primeira classe.

    O autor já separou decidido de não-decidido. Deixá-las como observação
    solta no relatório desfaria esse trabalho — e é justamente esse material
    que não pode ser gerado.
    """
    saida = []
    for numero, (texto, locator) in enumerate(pendencies, start=1):
        baixo = _sem_acento(texto).lower()
        de_seguranca = any(t in baixo for t in SAFETY_TERMS)
        de_terceiro = "fornecedor" in baixo or "confirmar com" in baixo
        estado = ("source_missing" if de_terceiro
                  else "human_decision_required")
        saida.append(Gap(
            kind="documented_pendency",
            subject="PEND-%03d" % numero,
            detail="[%s] %s" % (estado, texto[:400]),
            origin=Origin(document=documento, locator=locator, version=versao),
            # Segurança e handshake bloqueiam; o resto é registrado e segue.
            blocks_generation=de_seguranca or "handshake" in baixo))
    return saida


# =============================================================================
# adaptador .docx — a única parte que conhece Word
# =============================================================================

def read_docx_structure(path) -> dict:
    """`{headings, tables, paragraphs, pendencies}` de um `.docx`.

    Nenhuma semântica aqui. A associação tabela→sequência é POSICIONAL — a
    tabela pertence ao último título que a precede —, e por isso cada item
    carrega o índice do título, para que a decisão fique visível em vez de
    embutida.
    """
    import xml.etree.ElementTree as ET
    import zipfile

    W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
    with zipfile.ZipFile(str(path)) as z:
        doc = ET.fromstring(z.read("word/document.xml"))

    corpo = doc.find(W + "body")
    headings, tables, paragraphs, pendencies = [], [], [], []
    indice_titulo = -1
    dentro_de_pendencias = False
    contador = 0

    for elemento in list(corpo):
        etiqueta = elemento.tag
        if etiqueta == W + "p":
            texto = "".join(t.text or "" for t in elemento.iter(W + "t")).strip()
            estilo = elemento.find(W + "pPr/" + W + "pStyle")
            nome = estilo.get(W + "val") if estilo is not None else ""
            contador += 1
            if not texto:
                continue
            nivel = None
            if nome and ("Ttulo1" in nome or "Heading1" in nome):
                nivel = 1
            elif nome and ("Ttulo2" in nome or "Heading2" in nome):
                nivel = 2
            if nivel:
                indice_titulo = len(headings)
                headings.append((nivel, texto, "p%d" % contador))
                dentro_de_pendencias = (
                    nivel == 1 and _sem_acento(texto).upper().startswith("PEND"))
                continue
            if dentro_de_pendencias:
                pendencies.append((texto, "p%d" % contador))
            else:
                paragraphs.append((texto, "p%d" % contador, indice_titulo))
        elif etiqueta == W + "tbl":
            linhas = []
            for tr in elemento.iter(W + "tr"):
                celulas = ["".join(t.text or "" for t in tc.iter(W + "t")).strip()
                           for tc in tr.iter(W + "tc")]
                if any(celulas):
                    linhas.append(celulas)
            if len(linhas) < 2:
                continue
            cab = linhas[0]
            tables.append({
                "header": (cab[0] if cab else "", cab[1] if len(cab) > 1 else ""),
                "rows": [(l[0] if l else "", l[1] if len(l) > 1 else "")
                         for l in linhas[1:]],
                "after_heading": indice_titulo,
            })

    return {"headings": headings, "tables": tables,
            "paragraphs": paragraphs, "pendencies": pendencies}


def ingest_docx(path, *, inventory_tags, project: str = "planta",
                version: str | None = None) -> ProcessRequirements:
    import os

    estrutura = read_docx_structure(path)
    return ingest_sequences(
        headings=estrutura["headings"], tables=estrutura["tables"],
        paragraphs=estrutura["paragraphs"], pendencies=estrutura["pendencies"],
        inventory_tags=inventory_tags, document=os.path.basename(str(path)),
        version=version, project=project)

"""Seleção SEMÂNTICA de um nó da árvore de projeto — a identidade que
substitui `node_path` na fase R0b.

Este módulo roda no lado HOST (CPython 3), é puro e determinístico, e não abre
nenhum `.project`: ele recebe uma raiz e um adaptador de leitura
(`NodeView`) e devolve um veredito. O executor IronPython tem uma
reimplementação mínima da mesma regra — os dois runtimes não se importam, e a
duplicação é guardada por teste de igualdade do vocabulário
(`tests/unit/test_probe_46_executor.py`), não por confiança.

POR QUE ESTE MÓDULO EXISTE
==========================
`node_path` é caminho de ÍNDICES (`root/1/0/0`). O projeto-base foi trocado em
2026-07-31 por um template com cartões de I/O, e um cartão a mais sob o
`Device` desloca índices: o mesmo `root/1/0/0` passa a apontar para outro nó.
A medição de `docs/36` mostrou que, neste arquivo, `root/1/0/0` continua
valendo — mas continuar valendo **por sorte** é o pior resultado possível,
porque não se distingue de continuar valendo por construção.

A identidade passa a ser o que o nó É, não onde ele está:

    nome  +  type_guid  +  ancestralidade semântica  +  cardinalidade esperada

`node_path` continua sendo produzido — como DIAGNÓSTICO, dentro do resultado,
para que um humano saiba onde o nó foi achado. Nenhuma decisão deste módulo
depende dele.

FAIL-CLOSED: O QUE ESTE MÓDULO SE RECUSA A AFIRMAR
==================================================
A promessa de um seletor resolvido é forte — "existe exatamente UM nó que
casa" — e só pode ser feita sobre uma árvore inteiramente varrida. Por isso
três situações que um seletor ingênuo trataria como sucesso aqui NÃO
resolvem, cada uma com diagnóstico próprio:

* orçamento estourado (`selector_budget_exceeded`): a varredura parou no teto
  de nós/profundidade. Um único candidato encontrado até ali **não** autoriza
  concluir unicidade — o segundo pode estar exatamente no pedaço não varrido;
* nó ilegível (`selector_unreadable_node`): o adaptador levantou ao ler nome,
  type_guid ou filhos. Um nó cujo nome não pôde ser lido pode ser o segundo
  candidato, e uma lista de filhos ilegível esconde uma subárvore inteira;
* cardinalidade diferente da esperada: zero (`selector_no_match`) e dois ou
  mais (`selector_ambiguous`) são erros DISTINTOS, com nomes distintos, porque
  pedem ações opostas — um diz "o alvo não está aí", o outro diz "há mais de
  um alvo e o seletor não discrimina".

Um resultado não resolvido nunca carrega `node`. Não existe "melhor
candidato": escolher entre dois é exatamente o erro que a cardinalidade
existe para impedir.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Callable

SCHEMA_VERSION = 1

_GUID_RE = re.compile(
    r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-"
    r"[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$")

# --- vocabulário FECHADO de diagnóstico -------------------------------------
#
# Fechado de propósito: um chamador pode ramificar por estes nomes com a
# garantia de que um caso novo aparece como valor novo — e não escondido
# dentro de um "erro genérico" que ninguém trata.
DIAG_RESOLVED = "selector_resolved"
DIAG_NO_MATCH = "selector_no_match"
DIAG_AMBIGUOUS = "selector_ambiguous"
DIAG_INVALID = "selector_invalid"
DIAG_BUDGET_EXCEEDED = "selector_budget_exceeded"
DIAG_UNREADABLE = "selector_unreadable_node"

SELECTOR_DIAGNOSTICS = (
    DIAG_RESOLVED, DIAG_NO_MATCH, DIAG_AMBIGUOUS, DIAG_INVALID,
    DIAG_BUDGET_EXCEEDED, DIAG_UNREADABLE,
)

# Mesmos tetos do executor (`probes/46`), para que host e probe varram a mesma
# faixa. Teto não é limite de projeto: é a fronteira em que a árvore ainda é
# uma árvore de projeto, e não um objeto respondendo qualquer coisa.
DEFAULT_MAX_DEPTH = 8
DEFAULT_MAX_NODES = 1024
DEFAULT_MAX_CHILDREN = 128


class _Unreadable(Exception):
    """Interna. Sinaliza que o adaptador falhou ao ler um nó."""


@dataclass(frozen=True)
class NodeView:
    """Adaptador de leitura da árvore — a única superfície pelo qual este
    módulo toca um nó.

    Existe para que a regra de seleção seja testável sem MasterTool nenhum: no
    teste, os três callables leem objetos Python triviais; em produção, leem o
    objeto CLR. As três funções podem levantar — este módulo trata exceção
    como "nó ilegível", nunca como "nó que não casa", porque as duas coisas
    têm consequências opostas.
    """

    name_of: Callable[[Any], Any]
    type_guid_of: Callable[[Any], Any]
    children_of: Callable[[Any], Any]


@dataclass(frozen=True)
class SemanticSelector:
    """O que se procura, sem dizer onde está.

    `ancestor_names` é conferida como SUBSEQUÊNCIA ordenada da cadeia de
    ancestrais, não como caminho contíguo. Exigir contiguidade reintroduziria
    a suposição posicional que esta fase remove: um nível intermediário a mais
    (uma pasta nova, uma camada que outro produto insere) invalidaria um
    seletor que continua descrevendo corretamente o alvo. A unicidade não é
    garantida pela rigidez do caminho — é garantida pela cardinalidade,
    conferida sobre a árvore inteira.
    """

    name: str
    type_guid: str | None = None
    ancestor_names: tuple[str, ...] = ()
    expected_cardinality: int = 1
    max_depth: int = DEFAULT_MAX_DEPTH
    max_nodes: int = DEFAULT_MAX_NODES
    max_children: int = DEFAULT_MAX_CHILDREN


@dataclass(frozen=True)
class Candidate:
    """Um nó que casou. `node_path` é DIAGNÓSTICO — está aqui para o humano
    saber onde o nó foi achado, e nenhuma decisão o consome."""

    node: Any
    node_path: str
    name: str
    type_guid: str | None
    ancestor_names: tuple[str, ...]


@dataclass(frozen=True)
class SelectionResult:
    diagnostic: str
    message: str
    candidates: tuple[Candidate, ...] = ()
    visited: int = 0
    unreadable: int = 0
    problems: tuple[str, ...] = field(default_factory=tuple)

    @property
    def resolved(self) -> bool:
        return self.diagnostic == DIAG_RESOLVED

    @property
    def node(self) -> Any | None:
        """O nó, e só quando o veredito é `resolved` com cardinalidade 1.

        Deliberadamente `None` em qualquer outro caso: um resultado ambíguo
        que devolvesse "o primeiro" transformaria a recusa em escolha
        silenciosa.
        """
        if not self.resolved or len(self.candidates) != 1:
            return None
        return self.candidates[0].node


# --- parsing declarativo -----------------------------------------------------

_SELECTOR_REQUIRED = frozenset({"name"})
_SELECTOR_OPTIONAL = frozenset({
    "type_guid", "ancestor_names", "expected_cardinality",
    "max_depth", "max_nodes", "max_children",
})
_SELECTOR_ALLOWED = _SELECTOR_REQUIRED | _SELECTOR_OPTIONAL


def parse_selector(obj: Any) -> tuple[SemanticSelector | None, list[str]]:
    """Valida a forma declarativa de um seletor (a que vive dentro de um
    Template Profile). Nunca levanta: devolve `(None, problems)`.

    Campo desconhecido reprova, no mesmo espírito fail-closed de
    `spec/validator.py` e `templates/registry.py` — um seletor com
    `typeguid` (sem underscore) seria aceito em silêncio como "sem type_guid"
    e passaria a casar por nome apenas, que é uma seleção mais fraca do que a
    pedida.
    """
    problems: list[str] = []
    if not isinstance(obj, dict):
        return None, ["selector: esperado objeto, recebido %s" % type(obj).__name__]

    desconhecidos = sorted(set(obj) - _SELECTOR_ALLOWED)
    if desconhecidos:
        problems.append("selector: campo(s) desconhecido(s): %s"
                        % ", ".join(desconhecidos))
    faltando = sorted(_SELECTOR_REQUIRED - set(obj))
    if faltando:
        problems.append("selector: campo(s) obrigatório(s) ausente(s): %s"
                        % ", ".join(faltando))

    name = obj.get("name")
    if not isinstance(name, str) or not name.strip():
        problems.append("selector.name: esperado string não vazia")

    type_guid = obj.get("type_guid")
    if type_guid is not None:
        if not isinstance(type_guid, str) or not _GUID_RE.match(type_guid):
            problems.append("selector.type_guid: esperado GUID canônico ou "
                            "ausente — string vazia não é 'sem GUID'")

    ancestors_raw = obj.get("ancestor_names", [])
    ancestors: tuple[str, ...] = ()
    if not isinstance(ancestors_raw, (list, tuple)):
        problems.append("selector.ancestor_names: esperado lista de strings")
    else:
        ruins = [a for a in ancestors_raw
                 if not isinstance(a, str) or not a.strip()]
        if ruins:
            problems.append("selector.ancestor_names: todo item deve ser "
                            "string não vazia")
        else:
            ancestors = tuple(ancestors_raw)

    cardinalidade = obj.get("expected_cardinality", 1)
    if isinstance(cardinalidade, bool) or not isinstance(cardinalidade, int) \
            or cardinalidade < 1:
        problems.append("selector.expected_cardinality: esperado inteiro >= 1 "
                        "(zero não é cardinalidade: é ausência, e ausência se "
                        "declara não usando o seletor)")
        cardinalidade = 1

    tetos: dict[str, int] = {}
    for campo, padrao in (("max_depth", DEFAULT_MAX_DEPTH),
                          ("max_nodes", DEFAULT_MAX_NODES),
                          ("max_children", DEFAULT_MAX_CHILDREN)):
        valor = obj.get(campo, padrao)
        if isinstance(valor, bool) or not isinstance(valor, int) or valor < 1:
            problems.append("selector.%s: esperado inteiro >= 1" % campo)
            valor = padrao
        tetos[campo] = valor

    if problems:
        return None, problems

    return SemanticSelector(
        name=name,
        type_guid=type_guid,
        ancestor_names=ancestors,
        expected_cardinality=cardinalidade,
        max_depth=tetos["max_depth"],
        max_nodes=tetos["max_nodes"],
        max_children=tetos["max_children"],
    ), []


# --- a regra de casamento ----------------------------------------------------

def _is_subsequence(procurados: tuple[str, ...], cadeia: tuple[str, ...]) -> bool:
    """`procurados` aparece, na ordem, dentro de `cadeia`?"""
    it = iter(cadeia)
    return all(any(nome == candidato for candidato in it) for nome in procurados)


def matches(selector: SemanticSelector, name: Any, type_guid: Any,
            ancestor_names: tuple[str, ...]) -> bool:
    """Função pura de casamento, isolada para ser testada sem árvore.

    `type_guid` compara sem diferenciar maiúsculas: o produto devolve GUID em
    caixas diferentes conforme o acessor, e tratar isso como não-casamento
    seria recusar o nó certo por causa de formatação.
    """
    if name != selector.name:
        return False
    if selector.type_guid is not None:
        if not isinstance(type_guid, str):
            return False
        if type_guid.lower() != selector.type_guid.lower():
            return False
    if selector.ancestor_names:
        if not _is_subsequence(selector.ancestor_names, ancestor_names):
            return False
    return True


def _read(fn: Callable[[Any], Any], node: Any) -> Any:
    try:
        return fn(node)
    except Exception as exc:  # noqa: BLE001 — qualquer falha é ilegibilidade
        raise _Unreadable(str(exc) or exc.__class__.__name__)


def select_node(root: Any, selector: SemanticSelector,
                node_view: NodeView) -> SelectionResult:
    """Varre a árvore inteira sob `root` e devolve o veredito.

    A varredura é EXAUSTIVA por construção: não para no primeiro candidato,
    porque parar cedo tornaria a ambiguidade indetectável — e ambiguidade
    silenciosa é justamente o modo de falha que faz uma escrita acertar o
    objeto errado.

    Ordem determinística (pré-ordem, filhos por índice) para que `node_path`
    e a ordem dos candidatos sejam reproduzíveis entre execuções.
    """
    candidatos: list[Candidate] = []
    problemas: list[str] = []
    visitados = 0
    ilegiveis = 0
    estourou = False

    # Pilha de (nó, node_path, nomes dos ancestrais, profundidade).
    pilha: list[tuple[Any, str, tuple[str, ...], int]] = [(root, "root", (), 0)]

    while pilha:
        node, node_path, ancestrais, profundidade = pilha.pop()

        if visitados >= selector.max_nodes:
            estourou = True
            problemas.append(
                "teto de %d nós atingido antes de terminar a varredura"
                % selector.max_nodes)
            break
        visitados += 1

        # A RAIZ É O PROJETO, NÃO UM OBJETO DENTRO DELE.
        #
        # Medido no piloto de 2026-08-02: `ScriptProject` não expõe
        # `get_name`, e exigir nome da raiz produzia "nó ilegível" e recusa
        # antes de qualquer varredura útil. Ler nome de um projeto é erro de
        # categoria, não evidência de árvore ilegível.
        #
        # A raiz nunca é candidata — o que se exige dela é que os FILHOS
        # sejam alcançáveis, e essa exigência continua abaixo, intacta.
        eh_raiz = node_path == "root"
        nome = None
        if not eh_raiz:
            try:
                nome = _read(node_view.name_of, node)
            except _Unreadable as exc:
                ilegiveis += 1
                problemas.append("nome ilegível em %s: %s" % (node_path, exc))
                continue

            try:
                type_guid = _read(node_view.type_guid_of, node)
            except _Unreadable as exc:
                ilegiveis += 1
                problemas.append(
                    "type_guid ilegível em %s: %s" % (node_path, exc))
                continue

            if matches(selector, nome, type_guid, ancestrais):
                candidatos.append(Candidate(
                    node=node, node_path=node_path, name=nome,
                    type_guid=type_guid if isinstance(type_guid, str) else None,
                    ancestor_names=ancestrais))

        if profundidade >= selector.max_depth:
            # Não é erro: é o fundo declarado. Mas a subárvore abaixo não foi
            # varrida, e afirmar unicidade sobre o que não se varreu é
            # exatamente o que este módulo não faz.
            try:
                filhos = _read(node_view.children_of, node)
                tem_filhos = len(list(filhos)) > 0
            except Exception:  # noqa: BLE001
                tem_filhos = True
            if tem_filhos:
                estourou = True
                problemas.append(
                    "profundidade máxima (%d) atingida em %s com filhos não "
                    "varridos" % (selector.max_depth, node_path))
            continue

        try:
            filhos = list(_read(node_view.children_of, node))
        except _Unreadable as exc:
            ilegiveis += 1
            problemas.append(
                "filhos ilegíveis em %s (subárvore inteira não varrida): %s"
                % (node_path, exc))
            continue

        if len(filhos) > selector.max_children:
            estourou = True
            problemas.append(
                "%d filhos em %s excede o teto de %d — subárvore não varrida"
                % (len(filhos), node_path, selector.max_children))
            continue

        nomes_com_este = ancestrais + ((nome,) if isinstance(nome, str) else ())
        # Empilha em ordem reversa para que a visita saia em pré-ordem.
        for indice in range(len(filhos) - 1, -1, -1):
            pilha.append((filhos[indice],
                          "%s/%d" % (node_path, indice),
                          nomes_com_este,
                          profundidade + 1))

    ordenados = tuple(sorted(candidatos, key=lambda c: c.node_path))

    # A ORDEM DAS RECUSAS IMPORTA. Varredura incompleta vem primeiro: com um
    # pedaço da árvore não lido, "achei exatamente um" é uma afirmação que os
    # dados não sustentam, mesmo quando um candidato foi de fato encontrado.
    if ilegiveis:
        return SelectionResult(
            diagnostic=DIAG_UNREADABLE,
            message=("%d nó(s) ilegível(is) durante a varredura: a unicidade "
                     "do alvo não pode ser afirmada sobre árvore parcialmente "
                     "lida (%d candidato(s) encontrado(s) no que foi lido)"
                     % (ilegiveis, len(ordenados))),
            candidates=ordenados, visited=visitados, unreadable=ilegiveis,
            problems=tuple(problemas))

    if estourou:
        return SelectionResult(
            diagnostic=DIAG_BUDGET_EXCEEDED,
            message=("varredura incompleta: orçamento esgotado com %d nó(s) "
                     "visitado(s) e %d candidato(s) — um segundo alvo pode "
                     "estar na parte não varrida"
                     % (visitados, len(ordenados))),
            candidates=ordenados, visited=visitados, unreadable=0,
            problems=tuple(problemas))

    esperado = selector.expected_cardinality
    if len(ordenados) == esperado:
        return SelectionResult(
            diagnostic=DIAG_RESOLVED,
            message=("seletor resolvido: %d nó(s) com nome %r%s"
                     % (len(ordenados), selector.name,
                        "" if selector.type_guid is None
                        else " e type_guid %s" % selector.type_guid)),
            candidates=ordenados, visited=visitados, unreadable=0,
            problems=tuple(problemas))

    # Menos que o esperado é ausência, não ambiguidade — inclusive quando o
    # esperado é maior que um. Chamar de "ambíguo" um alvo que faltou mandaria
    # o operador discriminar melhor um seletor cujo problema é outro.
    if len(ordenados) < esperado:
        return SelectionResult(
            diagnostic=DIAG_NO_MATCH,
            message=("%d nó(s) casam com nome %r%s e %d era o esperado, em "
                     "%d nó(s) varrido(s)"
                     % (len(ordenados), selector.name,
                        "" if selector.type_guid is None
                        else " + type_guid %s" % selector.type_guid,
                        esperado, visitados)),
            candidates=ordenados, visited=visitados, unreadable=0,
            problems=tuple(problemas))

    return SelectionResult(
        diagnostic=DIAG_AMBIGUOUS,
        message=("seletor ambíguo: %d nó(s) casam e %d era o esperado — em %s"
                 % (len(ordenados), esperado,
                    ", ".join(c.node_path for c in ordenados[:8]))),
        candidates=ordenados, visited=visitados, unreadable=0,
        problems=tuple(problemas))

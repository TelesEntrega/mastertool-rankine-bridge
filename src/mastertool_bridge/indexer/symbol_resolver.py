"""Resolução de identificadores contra símbolos conhecidos do projeto.

Escopo estrito desta fatia (terceira do StaticProjectIndexer): dado o
conjunto de `PouSymbol` já extraído (fatia 1: `declaration_parser.py`/
`gvl_parser.py`) e as `Reference`/`Call` já extraídas sintaticamente (fatia
2: `statement_parser.py`), resolve cada identificador contra os escopos
conhecidos, seguindo uma prioridade estrita de níveis. NUNCA escolhe um
candidato arbitrariamente quando há ambiguidade — o resultado nesse caso é
sempre "ambiguous", nunca um palpite.

Esta fatia não lê nenhum arquivo nem faz IO — opera inteiramente sobre as
estruturas de dados já carregadas em memória, para ser testável de forma
determinística e barata.

Prioridade de resolução (para de subir de nível assim que há candidato(s)
em um nível; 2+ candidatos no MESMO nível = ambiguous, nunca desce nível):

    1/2. variável/parâmetro da POU atual (VAR/VAR_TEMP/VAR_STAT/VAR_INPUT/
         VAR_OUTPUT/VAR_IN_OUT do PouSymbol dono da referência) — shadowing
         entre os dois "sub-níveis" dentro da MESMA POU é ambiguous, não
         erro de parsing.
    3.   instância de FUNCTION_BLOCK: identificador bate com o NOME de uma
         variável da POU atual (nível 1/2) cujo `declared_type` bate com o
         `name` de um PouSymbol conhecido com pou_kind="FUNCTION_BLOCK".
    4.   GVL explícita: "NomeGvl.Variavel" onde NomeGvl é uma GVL conhecida
         e Variavel está entre suas `variables`.
    5.   GVL implícita: identificador bare batendo com variável de
         EXATAMENTE UMA GVL com is_qualified_only=False.
    6.   tipo: identificador bate com nome de PouSymbol (POU ou GVL) OU com
         declared_type/tipo base de alguma VariableDeclaration conhecida no
         projeto.
    7.   unresolved.

Cadeias pontuadas de 3+ segmentos ("GVL_Processo.InstanciaFB.Estado",
"GVL_Processo.InstanciaFB.Comando.Habilita", com ou sem índice de array no
meio, ex. "GVL_Processo.ArrayFB[i].Estado") são resolvidas por
`resolve_dotted_reference`, que generaliza o caso de 2 segmentos acima
caminhando por TODOS os segmentos da cadeia (ver docstring da função para o
algoritmo completo). Além de resolved/ambiguous/unresolved, esse caminho
pode produzir um quarto estado, `partially_resolved`: um PREFIXO da cadeia
foi confirmado com evidência (GVL existe, instância existe, tipo da
instância é conhecido), mas o(s) segmento(s) final(is) não puderam ser
confirmados (ex. o "membro" pedido não está entre as variáveis DECLARADAS
conhecidas do tipo — pode ser um método, propriedade, ou campo de uma
STRUCT/DUT que este indexador ainda não analisa). Nesse estado,
`resolved_prefix`/`unresolved_suffix`/`reason` ficam preenchidos.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

from mastertool_bridge.indexer.models import PouSymbol, TypeSymbol, VariableDeclaration

ResolutionState = Literal[
    "resolved", "partially_resolved", "ambiguous", "unresolved"
]

# Escopos considerados "variável/parâmetro da POU atual" (níveis 1/2 do
# enunciado, tratados como um único nível conforme permitido). Modificadores
# (" CONSTANT", " RETAIN" etc.) são sufixos do texto de `scope` (ver
# declaration_parser._consume_var_block_header) — por isso o teste de
# pertencimento usa prefixo, não igualdade exata.
_POU_LOCAL_SCOPE_PREFIXES = (
    "VAR",  # cobre VAR, VAR CONSTANT, VAR_TEMP, VAR_STAT, VAR_INPUT, ...
)
# Escopos que NUNCA contam como "local da POU atual" mesmo começando com VAR:
# apenas VAR_GLOBAL (blocos de GVL) fica de fora deste nível.
_NOT_POU_LOCAL_SCOPES_PREFIX = "VAR_GLOBAL"


@dataclass
class ResolvedSymbolRef:
    """Resultado da resolução de UM identificador (bare ou dotted) contra o
    modelo de símbolos do projeto."""

    state: ResolutionState
    rule_applied: str
    resolved_symbol: str | None = None
    """node_id do PouSymbol dono, quando aplicável (variável/parâmetro
    resolvido não tem node_id próprio no modelo atual — usamos o node_id do
    PouSymbol que a contém, já que VariableDeclaration não tem um; para FB
    instance / GVL / tipo o resolved_symbol é o node_id do PouSymbol alvo)."""
    candidates: list[str] = field(default_factory=list)
    variable: VariableDeclaration | None = None
    """Quando resolvido para uma variável concreta (níveis 1/2/4/5), guarda
    a própria VariableDeclaration para permitir checagem de scope (ex.
    VAR_IN_OUT) por quem for classificar read/write."""
    fb_type_symbol: PouSymbol | TypeSymbol | None = None
    """Quando resolvido como instância de FB (nível 3), guarda o PouSymbol
    do TIPO do FB (para permitir resolução de chamadas/métodos a partir da
    instância). A partir da FASE 2 do STRUCT/DUT, quando a cadeia termina
    num container STRUCT navegável, este campo pode também guardar o
    TypeSymbol final (para uso analítico/depuração) — consumidores que
    tratam este campo como "instância de FB chamável" (ex.
    `call_resolver._resolve_method_call`) continuam corretos: um TypeSymbol
    aqui nunca é produzido no CAMINHO usado por chamadas de método, apenas
    quando o ÚLTIMO segmento de uma cadeia de REFERÊNCIA (não callee) é um
    membro cujo tipo é STRUCT."""
    message: str = ""
    resolved_prefix: str | None = None
    """Quando state="partially_resolved": texto do PREFIXO da cadeia já
    confirmado (ex. "GVL_Processo.InstanciaFB"), incluindo qualquer sufixo
    de índice `[...]` presente nos segmentos confirmados, para exibição."""
    unresolved_suffix: str | None = None
    """Quando state="partially_resolved": texto do(s) segmento(s)
    restante(s) da cadeia que não puderam ser confirmados (ex. "Estado")."""
    reason: str | None = None
    """Quando state="partially_resolved": motivo textual pelo qual o(s)
    segmento(s) restante(s) não puderam ser confirmados (ex. "member
    metadata unavailable", "tipo da instância desconhecido/não analisável")."""


class ProjectSymbolIndex:
    """Índice em memória de todos os `PouSymbol` de um projeto, construído
    uma vez e reutilizado para resolver múltiplos identificadores."""

    def __init__(
        self,
        symbols: list[PouSymbol],
        type_symbols: list[TypeSymbol] | None = None,
    ) -> None:
        self.symbols = symbols
        self.by_node_id: dict[str, PouSymbol] = {s.node_id: s for s in symbols}
        self.by_name: dict[str, list[PouSymbol]] = {}
        for s in symbols:
            self.by_name.setdefault(s.name, []).append(s)

        # Mudança ADITIVA e RETROCOMPATÍVEL: `type_symbols` é opcional
        # (default None/vazio) — todo `ProjectSymbolIndex(symbols)` já
        # existente continua funcionando sem passar este parâmetro. Nesta
        # fase o índice apenas CONHECE os TypeSymbol (STRUCT/alias/unknown
        # de DUT); a caminhada de cadeia (resolve_identifier/
        # resolve_dotted_reference/_container_from_declared_type/
        # _walk_remaining_segments) ainda NÃO os utiliza — isso é FASE 2.
        self.type_symbols: list[TypeSymbol] = list(type_symbols or [])
        self.types_by_name: dict[str, list[TypeSymbol]] = {}
        for t in self.type_symbols:
            self.types_by_name.setdefault(t.name, []).append(t)

        self.function_blocks_by_name: dict[str, list[PouSymbol]] = {}
        self.functions_by_name: dict[str, list[PouSymbol]] = {}
        self.programs_by_name: dict[str, list[PouSymbol]] = {}
        """Índice pou_kind="PROGRAM" -> lista de PouSymbol com aquele nome.
        Usado por `call_resolver._resolve_one_call` para o nível "chamada
        direta a PROGRAM": no dialeto CODESYS uma PROGRAM chama outra
        PROGRAM pelo NOME diretamente, sem instância local (diferente de
        FUNCTION_BLOCK, que sempre precisa de uma variável de instância)."""
        self.gvls_by_name: dict[str, list[PouSymbol]] = {}
        for s in symbols:
            if s.pou_kind == "FUNCTION_BLOCK":
                self.function_blocks_by_name.setdefault(s.name, []).append(s)
            elif s.pou_kind == "FUNCTION":
                self.functions_by_name.setdefault(s.name, []).append(s)
            elif s.pou_kind == "PROGRAM":
                self.programs_by_name.setdefault(s.name, []).append(s)
            elif s.pou_kind == "GVL":
                self.gvls_by_name.setdefault(s.name, []).append(s)

        # Índice nível 5 (GVL implícita): nome de variável -> lista de GVLs
        # elegíveis (is_qualified_only=False) que a declaram.
        self._implicit_gvl_var_index: dict[str, list[tuple[PouSymbol, VariableDeclaration]]] = {}
        for s in symbols:
            if s.pou_kind != "GVL" or s.is_qualified_only:
                continue
            for var in s.variables:
                self._implicit_gvl_var_index.setdefault(var.name, []).append((s, var))

        # Índice nível 6 (tipo): todo tipo textual usado em alguma
        # VariableDeclaration conhecida no projeto (declared_type — para
        # ARRAY isso já é o texto completo "ARRAY[..] OF X" produzido pelo
        # parser, então também indexamos separadamente o tipo BASE quando
        # for ARRAY, usando array_dimensions/is_array como sinal).
        self._known_declared_types: set[str] = set()
        self._known_base_types: set[str] = set()
        for s in symbols:
            for var in s.variables:
                self._known_declared_types.add(var.declared_type)
                if var.is_array:
                    base = _array_base_type(var.declared_type)
                    if base:
                        self._known_base_types.add(base)

    def pou_by_node_id(self, node_id: str) -> PouSymbol | None:
        return self.by_node_id.get(node_id)

    def is_known_type_name(self, name: str) -> bool:
        if name in self.by_name:
            return True
        if name in self._known_declared_types:
            return True
        if name in self._known_base_types:
            return True
        return False


def _array_base_type(declared_type: str) -> str | None:
    """Extrai o tipo base textual de um `declared_type` no formato
    'ARRAY[dims] OF BASE' produzido por declaration_parser._parse_type.
    Retorna None se não estiver nesse formato (best-effort, sem lançar)."""
    marker = " OF "
    idx = declared_type.upper().rfind(marker)
    if idx == -1:
        return None
    return declared_type[idx + len(marker):].strip() or None


def resolve_alias_target(
    type_symbol: TypeSymbol, index: ProjectSymbolIndex
) -> TypeSymbol | None:
    """Resolve o TypeSymbol FINAL de uma cadeia de alias (`TYPE X : Y;`).

    Se `type_symbol.kind != "alias"`, retorna o próprio `type_symbol`
    (nada a resolver). Caso contrário, segue `alias_target` recursivamente
    através de `index.types_by_name`, mantendo um SET de nomes já visitados:

      - nome já visitado (CICLO, ex. `TYPE A : B; TYPE B : A;`) -> None,
        nunca trava em loop infinito, nunca lança exceção;
      - alvo do alias ausente em `types_by_name`, ou ambíguo (2+ TypeSymbol
        com o mesmo nome) -> None (honesto: esta função só entrega o
        TypeSymbol final ou None — a FASE 2 decide como reportar isso).

    Não caminha por `members`/estrutura de STRUCT — apenas a cadeia de
    aliases em si."""
    current = type_symbol
    visited: set[str] = set()

    while current.kind == "alias":
        if current.name in visited:
            return None
        visited.add(current.name)

        target_name = current.alias_target
        if target_name is None:
            return None

        candidates = index.types_by_name.get(target_name, [])
        if len(candidates) != 1:
            return None

        current = candidates[0]

    return current


def owner_node_id_from_node_id(node_id: str) -> str:
    """Extrai o node_id do PouSymbol dono a partir do node_id de uma
    Reference/Call/Statement (formato "<owner_node_id>#stmtN"). Se não
    houver '#', assume que o próprio node_id já é o do owner (defensivo,
    nunca lança)."""
    return node_id.split("#", 1)[0]


def find_pou_local_variable(
    pou: PouSymbol, name: str
) -> tuple[ResolutionState, list[VariableDeclaration]]:
    """Procura `name` entre as variáveis locais/parâmetros da POU (níveis
    1/2 unificados). Retorna (state, candidatos) — candidatos tem 0, 1 ou 2+
    elementos (2+ = shadowing intra-POU = ambiguous)."""
    matches = [
        v
        for v in pou.variables
        if v.name == name and not v.scope.upper().startswith(_NOT_POU_LOCAL_SCOPES_PREFIX)
    ]
    if not matches:
        return "unresolved", []
    if len(matches) == 1:
        return "resolved", matches
    return "ambiguous", matches


def resolve_identifier(
    name: str,
    owner_pou: PouSymbol | None,
    index: ProjectSymbolIndex,
) -> ResolvedSymbolRef:
    """Resolve um identificador BARE (sem ponto) contra a prioridade de
    níveis 1/2 -> 3 -> 5 -> 6 -> 7 (nível 4, GVL explícita, é tratado por
    `resolve_dotted_reference` para nomes com ponto — um nome bare nunca
    passa pelo nível 4)."""
    # Níveis 1/2: variável/parâmetro local da POU atual.
    if owner_pou is not None:
        state, matches = find_pou_local_variable(owner_pou, name)
        if state == "ambiguous":
            return ResolvedSymbolRef(
                state="ambiguous",
                rule_applied="pou_local_shadowing",
                resolved_symbol=owner_pou.node_id,
                candidates=[owner_pou.node_id] * len(matches),
                message=(
                    f"Identificador {name!r} declarado mais de uma vez em "
                    f"escopos diferentes da mesma POU {owner_pou.name!r} "
                    "(shadowing intra-POU)."
                ),
            )
        if state == "resolved":
            var = matches[0]
            # Nível 3: instância de FUNCTION_BLOCK?
            fb_candidates = index.function_blocks_by_name.get(var.declared_type, [])
            if len(fb_candidates) == 1:
                return ResolvedSymbolRef(
                    state="resolved",
                    rule_applied="fb_instance",
                    resolved_symbol=owner_pou.node_id,
                    variable=var,
                    fb_type_symbol=fb_candidates[0],
                )
            if len(fb_candidates) > 1:
                return ResolvedSymbolRef(
                    state="ambiguous",
                    rule_applied="fb_instance",
                    candidates=[s.node_id for s in fb_candidates],
                    variable=var,
                    message=(
                        f"Tipo declarado {var.declared_type!r} da variável "
                        f"{name!r} bate com mais de um PouSymbol "
                        "FUNCTION_BLOCK conhecido."
                    ),
                )
            # Variável local comum (não é instância de FB conhecido).
            return ResolvedSymbolRef(
                state="resolved",
                rule_applied="local_variable"
                if _is_local_only_scope(var.scope)
                else "pou_parameter",
                resolved_symbol=owner_pou.node_id,
                variable=var,
            )

    # Nível 5: GVL implícita (bare, apenas GVLs is_qualified_only=False).
    gvl_matches = index._implicit_gvl_var_index.get(name, [])
    if len(gvl_matches) == 1:
        gvl_symbol, var = gvl_matches[0]
        return ResolvedSymbolRef(
            state="resolved",
            rule_applied="gvl_implicit",
            resolved_symbol=gvl_symbol.node_id,
            variable=var,
        )
    if len(gvl_matches) > 1:
        return ResolvedSymbolRef(
            state="ambiguous",
            rule_applied="gvl_implicit",
            candidates=[s.node_id for s, _v in gvl_matches],
            message=(
                f"Identificador {name!r} encontrado em mais de uma GVL "
                "não-qualified_only (referência bare ambígua)."
            ),
        )

    # Nível 6: tipo (nome de PouSymbol OU declared_type/tipo-base conhecido).
    if index.is_known_type_name(name):
        type_symbols = index.by_name.get(name, [])
        if len(type_symbols) == 1:
            return ResolvedSymbolRef(
                state="resolved",
                rule_applied="type_reference",
                resolved_symbol=type_symbols[0].node_id,
            )
        if len(type_symbols) > 1:
            return ResolvedSymbolRef(
                state="ambiguous",
                rule_applied="type_reference",
                candidates=[s.node_id for s in type_symbols],
                message=(
                    f"Nome de tipo {name!r} bate com mais de um PouSymbol "
                    "conhecido."
                ),
            )
        # Só aparece como declared_type/tipo-base de variáveis (não é o
        # nome de nenhuma POU/GVL conhecida) — resolvido como referência a
        # tipo, mas sem um PouSymbol concreto para apontar.
        return ResolvedSymbolRef(
            state="resolved",
            rule_applied="type_reference",
            resolved_symbol=None,
        )

    # Nível 7: unresolved.
    return ResolvedSymbolRef(
        state="unresolved",
        rule_applied="none",
        message=f"Nenhum símbolo com o nome {name!r} foi encontrado em nenhum escopo conhecido.",
    )


def _is_local_only_scope(scope: str) -> bool:
    upper = scope.upper()
    return upper.startswith("VAR ") or upper == "VAR" or upper.startswith("VAR_TEMP") or upper.startswith("VAR_STAT")


def _split_dotted_chain_segments(full_name: str) -> list[str]:
    """Divide `full_name` em segmentos por '.', respeitando aninhamento de
    `[...]` (um '.' dentro de um índice, ex. de uma expressão aritmética ou
    de acesso a struct dentro do índice, NUNCA separa segmentos — best-
    effort, mas não deveria ocorrer na prática já que o texto do índice em
    si não costuma conter '.'; a robustez aqui é apenas defensiva). Cada
    segmento retornado preserva seu eventual sufixo `[...]` bruto (ex.
    "ArrayInstancias[i]"), para exibição em `resolved_prefix`/
    `unresolved_suffix` — a remoção do índice para fins de LOOKUP de nome de
    variável é feita separadamente por `_segment_bare_name`."""
    segments: list[str] = []
    current: list[str] = []
    depth = 0
    for ch in full_name:
        if ch == "[":
            depth += 1
            current.append(ch)
        elif ch == "]":
            depth = max(0, depth - 1)
            current.append(ch)
        elif ch == "." and depth == 0:
            segments.append("".join(current))
            current = []
        else:
            current.append(ch)
    segments.append("".join(current))
    return [s for s in segments if s]


def _segment_bare_name(segment: str) -> str:
    """Remove qualquer sufixo `[...]` de um segmento de cadeia, retornando
    apenas o nome do identificador a ser buscado entre `variables` (o
    índice em si não afeta QUAL variável está sendo referenciada — só
    precisa ser preservado no texto para exibição, nunca na busca)."""
    idx = segment.find("[")
    return segment[:idx] if idx != -1 else segment


def _container_from_declared_type(
    declared_type: str, index: ProjectSymbolIndex
) -> PouSymbol | TypeSymbol | None:
    """Se `declared_type` (ou seu tipo base, quando ARRAY[..] OF X) bate com
    EXATAMENTE UM PouSymbol FUNCTION_BLOCK conhecido, retorna aquele
    PouSymbol para continuar a caminhada da cadeia por seus `variables`.

    Caso contrário, tenta a mesma busca (nome exato, depois tipo BASE de
    ARRAY[..] OF X) contra `index.types_by_name` (STRUCT/alias de DUT — ver
    `models.TypeSymbol`, FASE 1): se achar exatamente 1 TypeSymbol, segue
    `resolve_alias_target` até chegar a um TypeSymbol final (kind="struct"
    navegável, kind="unknown" ex. ENUM — tratado pelo CHAMADOR como
    "container None" mas sem esconder que o tipo existe, ver
    `_walk_remaining_segments`), ou None (ciclo/alvo ausente/ambíguo).

    Retorna None quando o tipo é primitivo, completamente desconhecido, ou
    ambíguo em qualquer um dos dois níveis (2+ FUNCTION_BLOCK OU 2+
    TypeSymbol com mesmo nome — tratado à parte pelo chamador para virar
    "ambiguous", não silenciosamente None; ver `fb_candidates_for_declared_type`/
    `type_candidates_for_declared_type`)."""
    fb_candidates = index.function_blocks_by_name.get(declared_type, [])
    if len(fb_candidates) == 1:
        return fb_candidates[0]
    if len(fb_candidates) > 1:
        return None  # ambiguidade tratada pelo chamador via nome cru
    if not fb_candidates:
        base = _array_base_type(declared_type)
        if base:
            base_candidates = index.function_blocks_by_name.get(base, [])
            if len(base_candidates) == 1:
                return base_candidates[0]
            if len(base_candidates) > 1:
                return None  # ambiguidade tratada pelo chamador

    type_candidates = type_candidates_for_declared_type(declared_type, index)
    if len(type_candidates) == 1:
        return resolve_alias_target(type_candidates[0], index)
    return None  # 0 ou 2+ candidatos: nenhum tipo conhecido, ou ambiguidade


def fb_candidates_for_declared_type(
    declared_type: str, index: ProjectSymbolIndex
) -> list[PouSymbol]:
    """Lista de PouSymbol FUNCTION_BLOCK cujo nome bate com `declared_type`
    (ou seu tipo base, se ARRAY[..] OF X) — usada para distinguir
    "nenhum candidato" (tipo desconhecido/primitivo/DUT) de "2+ candidatos"
    (ambiguidade), já que `_container_from_declared_type` colapsa os dois
    casos em None."""
    fb_candidates = index.function_blocks_by_name.get(declared_type, [])
    if fb_candidates:
        return fb_candidates
    base = _array_base_type(declared_type)
    if base:
        return index.function_blocks_by_name.get(base, [])
    return []


def type_candidates_for_declared_type(
    declared_type: str, index: ProjectSymbolIndex
) -> list[TypeSymbol]:
    """Análogo a `fb_candidates_for_declared_type`, mas para
    `index.types_by_name` (STRUCT/alias de DUT) — permite ao chamador
    distinguir "nenhum candidato" (tipo primitivo/desconhecido) de "2+
    candidatos" (ambiguidade de nome de tipo), sem que
    `_container_from_declared_type` colapse os dois casos em None."""
    type_candidates = index.types_by_name.get(declared_type, [])
    if type_candidates:
        return type_candidates
    base = _array_base_type(declared_type)
    if base:
        return index.types_by_name.get(base, [])
    return []


def _container_member_list(
    container: PouSymbol | TypeSymbol | None,
) -> list[VariableDeclaration]:
    """Adaptador: `PouSymbol.variables` e `TypeSymbol.members` guardam a
    mesma coisa (lista de `VariableDeclaration`) sob nomes de atributo
    diferentes (decisão deliberada da FASE 1 — ver docstring de
    `models.TypeSymbol`). Usado por `_walk_remaining_segments` para navegar
    ambos os tipos de container uniformemente."""
    if isinstance(container, PouSymbol):
        return container.variables
    if isinstance(container, TypeSymbol):
        return container.members
    return []


def resolve_dotted_reference(
    full_name: str,
    owner_pou: PouSymbol | None,
    index: ProjectSymbolIndex,
) -> ResolvedSymbolRef:
    """Resolve um identificador com ponto ("Prefixo.Meio.Resto...", N>=2
    segmentos), caminhando por TODOS os segmentos da cadeia (generalização
    do caso de 2 segmentos). Suporta sufixo de índice de array em qualquer
    segmento (ex. "GVL_A.ArrayInstancias[i].Estado") — o índice é ignorado
    na busca por nome de variável, mas preservado no texto de
    `resolved_prefix`/`unresolved_suffix` para exibição.

    Algoritmo (sem NUNCA adivinhar um membro que não está entre as
    `variables` conhecidas de um tipo — ausência de evidência sempre vira
    `partially_resolved` ou `unresolved`, nunca `resolved` por suposição):

      1. Primeiro segmento: resolvido pela MESMA prioridade usada para
         identificadores bare (`resolve_identifier`), ACRESCIDA da
         prioridade de GVL explícita (nível 4) quando o primeiro segmento
         bate com o nome de uma GVL conhecida (só faz sentido para cadeias,
         nunca para um nome bare sem ponto). Se o primeiro segmento já for
         unresolved, a cadeia INTEIRA é unresolved (nunca
         `partially_resolved` sem nenhum prefixo confirmado — ex.
         "SysTimeCore.SysTimeGetUs", biblioteca externa, honestamente
         unresolved).
      2. Para cada segmento seguinte: precisa de um "container" (PouSymbol
         cujas `variables` serão buscadas) estabelecido pelo segmento
         anterior — uma GVL (nível 4) ou um FUNCTION_BLOCK conhecido (nível
         3, inclusive o tipo BASE de um ARRAY[..] OF FB_X). Busca o próximo
         segmento (removendo o sufixo `[...]` antes de comparar) entre as
         `variables` do container:
           - exatamente 1 variável com esse nome -> continua para o
             próximo segmento, atualizando o container conforme o
             `declared_type` dessa variável;
           - 2+ variáveis com o mesmo nome no mesmo container -> ambiguous;
           - nenhuma variável com esse nome -> partially_resolved
             (resolved_prefix = segmentos já confirmados, unresolved_suffix
             = segmentos restantes, reason="member metadata unavailable");
           - container ficou None (tipo anterior não é FB/GVL conhecido,
             ex. primitivo ou DUT/STRUCT não analisado) mas ainda restam
             segmentos -> partially_resolved (mesmo raciocínio: o prefixo
             já confirmado permanece válido, mas não é possível verificar
             mais fundo).
      3. Se todos os segmentos foram consumidos com sucesso -> resolved.
    """
    segments = _split_dotted_chain_segments(full_name)
    if len(segments) <= 1:
        return resolve_identifier(full_name, owner_pou, index)

    first_bare = _segment_bare_name(segments[0])

    # --- Passo 1: resolve o primeiro segmento. ----------------------------
    #
    # Nível 4 (GVL explícita) primeiro: só se aplica a cadeias (nunca a um
    # nome bare), e só quando o primeiro segmento bate com o nome de uma
    # GVL conhecida. Precisa ser tentado ANTES da prioridade padrão porque
    # `resolve_identifier` não conhece o nível 4.
    gvl_candidates = index.gvls_by_name.get(first_bare, [])
    if len(gvl_candidates) == 1:
        container: PouSymbol | None = gvl_candidates[0]
        confirmed_segments = [segments[0]]
        return _walk_remaining_segments(
            container,
            container.node_id,
            confirmed_segments,
            segments[1:],
            index,
            # Nome de regra do caso de 2 segmentos preservado por
            # compatibilidade (não-regressão do comportamento já existente
            # e testado antes desta generalização); cadeias mais longas
            # usam o nome genérico "dotted_chain".
            two_segment_rule_name="gvl_explicit",
        )
    if len(gvl_candidates) > 1:
        return ResolvedSymbolRef(
            state="ambiguous",
            rule_applied="gvl_explicit",
            candidates=[s.node_id for s in gvl_candidates],
            message=f"Mais de uma GVL conhecida chamada {first_bare!r}.",
        )

    # Sem GVL candidata: aplica a MESMA prioridade de identificador bare
    # (níveis 1/2 -> 3 -> 5 -> 6 -> 7) ao primeiro segmento.
    first_result = resolve_identifier(first_bare, owner_pou, index)

    if first_result.state == "unresolved":
        # Primeiro segmento não bate com nada conhecido -> cadeia inteira
        # honestamente unresolved, NUNCA partially_resolved sem nenhum
        # prefixo confirmado (ex. biblioteca externa "SysTimeCore.Foo").
        return ResolvedSymbolRef(
            state="unresolved",
            rule_applied="none",
            message=(
                f"Primeiro segmento {first_bare!r} da cadeia {full_name!r} "
                "não bate com nenhum símbolo conhecido (variável local, "
                "instância de FB, GVL ou tipo)."
            ),
        )
    if first_result.state == "ambiguous":
        return first_result

    # first_result.state == "resolved": determina o container para o
    # próximo segmento a partir da regra aplicada, e o node_id "dono" do
    # primeiro segmento em si (owner_pou para variável local/parâmetro, ou
    # a GVL para gvl_implicit) -- este último é o resolved_symbol a usar se
    # o SEGUNDO segmento em diante não puder ser confirmado (o primeiro
    # segmento continua válido mesmo assim).
    confirmed_segments = [segments[0]]
    first_owner_node_id = first_result.resolved_symbol
    if first_result.rule_applied == "fb_instance" and first_result.fb_type_symbol is not None:
        container = first_result.fb_type_symbol
    elif first_result.rule_applied == "gvl_implicit" and first_result.resolved_symbol is not None:
        container = index.pou_by_node_id(first_result.resolved_symbol)
    elif first_result.variable is not None:
        # Variável comum (não instância de FB conhecido) resolvida no nível
        # 1/2 ou 5 -- tenta o declared_type dela mesmo assim (defensivo,
        # cobre o caso em que o `declared_type` é um FB mas por algum
        # motivo `resolve_identifier` não marcou como fb_instance).
        container = _container_from_declared_type(first_result.variable.declared_type, index)
    else:
        # type_reference ou outra regra que não estabelece um container de
        # variáveis navegável -- não há como confirmar mais segmentos.
        container = None

    return _walk_remaining_segments(
        container, first_owner_node_id, confirmed_segments, segments[1:], index
    )


def _walk_remaining_segments(
    container: PouSymbol | TypeSymbol | None,
    initial_owner_node_id: str | None,
    confirmed_segments: list[str],
    remaining_segments: list[str],
    index: ProjectSymbolIndex,
    two_segment_rule_name: str | None = None,
) -> ResolvedSymbolRef:
    """Passo 2 do algoritmo: caminha pelos segmentos restantes da cadeia,
    um de cada vez, usando `container` (PouSymbol cujas `variables` serão
    buscadas) estabelecido pelo(s) segmento(s) já confirmado(s). Nunca
    lança; sempre retorna resolved/partially_resolved/ambiguous.

    `two_segment_rule_name`, quando informado, é o `rule_applied` a usar
    SE a cadeia inteira tiver exatamente 2 segmentos E resolver com
    sucesso (preserva nomes de regra de comportamento pré-existente, ex.
    "gvl_explicit", para não quebrar não-regressão de testes/consumidores
    já escritos contra o caso de 2 segmentos)."""
    last_variable: VariableDeclaration | None = None
    last_container = container
    # node_id do PouSymbol/TypeSymbol DONO do último segmento confirmado --
    # distinto de `last_container`, que após confirmar um segmento avança
    # para o TIPO daquela variável (o próximo container a navegar).
    # Inicializado com o "dono" do PRIMEIRO segmento (owner_pou da variável
    # local, ou a própria GVL), para que uma cadeia que pare logo no 2º
    # segmento (ex. tipo de instância desconhecido) ainda aponte
    # resolved_symbol para o símbolo do primeiro segmento, já confirmado.
    owner_node_id: str | None = initial_owner_node_id

    for pos, raw_segment in enumerate(remaining_segments):
        bare_name = _segment_bare_name(raw_segment)

        if last_container is None:
            # Segmento anterior não estabeleceu um container navegável
            # (tipo primitivo, completamente desconhecido, alias cíclico/
            # inexistente/ambíguo) mas ainda restam segmentos -- o prefixo
            # já confirmado permanece válido, mas não é possível verificar
            # mais fundo.
            return _partially_resolved(
                confirmed_segments,
                [raw_segment, *remaining_segments[pos + 1 :]],
                reason=(
                    "tipo do segmento anterior é desconhecido, primitivo, ou "
                    "um alias/tipo não resolvível (ciclo, alvo ausente ou "
                    "ambíguo)"
                ),
                last_variable=last_variable,
                last_container_node_id=owner_node_id,
            )

        if isinstance(last_container, TypeSymbol) and last_container.kind == "unknown":
            # Tipo reconhecido (ex. ENUM) mas não indexado como STRUCT nesta
            # fase -- tratado como "container None" no fluxo, mas SEM
            # esconder que o tipo existe (reason específico).
            return _partially_resolved(
                confirmed_segments,
                [raw_segment, *remaining_segments[pos + 1 :]],
                reason=(
                    "tipo reconhecido (enum) mas não indexado como STRUCT "
                    "nesta fase"
                ),
                last_variable=last_variable,
                last_container_node_id=owner_node_id,
            )

        member_list = _container_member_list(last_container)
        var_matches = [v for v in member_list if v.name == bare_name]
        if len(var_matches) > 1:
            return ResolvedSymbolRef(
                state="ambiguous",
                rule_applied="dotted_chain_member_shadowing",
                candidates=[last_container.node_id] * len(var_matches),
                message=(
                    f"{last_container.name!r} declara mais de uma variável "
                    f"chamada {bare_name!r} (cadeia "
                    f"{'.'.join(confirmed_segments)!r})."
                ),
            )
        if not var_matches:
            # Membro pedido não está entre as variáveis DECLARADAS
            # conhecidas do container. Para FUNCTION_BLOCK isso pode ser um
            # método/propriedade fora do modelo de dados ("member metadata
            # unavailable"); para TypeSymbol kind="struct" o indexador TEM
            # os dados completos do tipo e ainda assim não achou o membro --
            # afirmação mais forte, reason distinto e EXATO conforme pedido.
            reason = (
                "member_not_found_in_indexed_type"
                if isinstance(last_container, TypeSymbol)
                else "member metadata unavailable"
            )
            return _partially_resolved(
                confirmed_segments,
                [raw_segment, *remaining_segments[pos + 1 :]],
                reason=reason,
                last_variable=last_variable,
                last_container_node_id=last_container.node_id,
            )

        # Exatamente 1 variável encontrada: confirma este segmento e
        # continua a caminhada com o container do PRÓXIMO nível.
        owner_node_id = last_container.node_id
        last_variable = var_matches[0]
        confirmed_segments = [*confirmed_segments, raw_segment]
        last_container = _container_from_declared_type(last_variable.declared_type, index)

    # Todos os segmentos consumidos com sucesso: resolved_symbol aponta
    # para o PouSymbol DONO da última variável confirmada (onde ela está
    # declarada em `variables`), permitindo que quem consome este resultado
    # (ex. read-write-index.json) agregue a ocorrência sob um símbolo útil.
    total_segments = len(confirmed_segments)
    rule_applied = (
        two_segment_rule_name
        if total_segments == 2 and two_segment_rule_name
        else "dotted_chain"
    )
    return ResolvedSymbolRef(
        state="resolved",
        rule_applied=rule_applied,
        resolved_symbol=owner_node_id,
        variable=last_variable,
        fb_type_symbol=last_container,
    )


def _partially_resolved(
    confirmed_segments: list[str],
    unresolved_segments: list[str],
    reason: str,
    last_variable: VariableDeclaration | None,
    last_container_node_id: str | None,
) -> ResolvedSymbolRef:
    return ResolvedSymbolRef(
        state="partially_resolved",
        rule_applied="dotted_chain_partial",
        resolved_symbol=last_container_node_id,
        variable=last_variable,
        resolved_prefix=".".join(confirmed_segments),
        unresolved_suffix=".".join(unresolved_segments),
        reason=reason,
        message=(
            f"Prefixo {'.'.join(confirmed_segments)!r} confirmado, mas "
            f"{'.'.join(unresolved_segments)!r} não pôde ser confirmado "
            f"({reason})."
        ),
    )

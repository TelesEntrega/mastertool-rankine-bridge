"""Parser determinístico de intenção de consulta em linguagem natural.

Módulo PURO — zero dependência de `query.py`, `symbol_resolver.py` ou
qualquer outro módulo do pacote `indexer`. Usa APENAS stdlib (`dataclasses`,
`re`, `unicodedata`). Não faz IO, não reprocessa ST, não conhece o índice.

Reconhece um conjunto FECHADO de templates (português + inglês canônico) e
produz um `QueryIntent` com 4 estados possíveis:

    matched      -- exatamente UMA das 5 operações reconhecida, com target.
    ambiguous    -- família "uso" (não distingue leitura de escrita).
    unsupported  -- pergunta de explicação/raciocínio (fora de escopo) OU
                    nenhum template reconhecido (mas entrada bem formada).
    invalid      -- entrada malformada (vazia, sem target, duas perguntas
                    coladas).

Nenhuma IA/LLM, embeddings, fuzzy matching, correção ortográfica ou
sinônimos além dos listados explicitamente nos templates abaixo. "Uso"
NUNCA é interpretado como leitura OU escrita -- sempre ambíguo com os dois
candidatos.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field

# ---------------------------------------------------------------------------
# accent folding (stdlib apenas -- unicodedata)
# ---------------------------------------------------------------------------


def accent_fold(s: str) -> str:
    """Remove marcas diacríticas preservando a contagem de caracteres (1
    caractere acentuado -> 1 caractere base), essencial para que offsets de
    span calculados sobre o texto "folded" continuem válidos ao fatiar o
    texto ORIGINAL (mesmo alinhamento 1:1)."""
    decomposed = unicodedata.normalize("NFKD", s)
    return "".join(ch for ch in decomposed if not unicodedata.combining(ch))


# ---------------------------------------------------------------------------
# QueryIntent
# ---------------------------------------------------------------------------


@dataclass
class QueryIntent:
    status: str  # "matched" | "ambiguous" | "unsupported" | "invalid"
    operation: str | None = None
    target: str | None = None
    matched_pattern: str | None = None
    confidence: str = "none"
    reason: str | None = None
    candidates: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        data: dict = {
            "status": self.status,
            "operation": self.operation,
            "target": self.target,
            "matched_pattern": self.matched_pattern,
            "confidence": self.confidence,
        }
        if self.reason is not None:
            data["reason"] = self.reason
        if self.candidates:
            data["candidates"] = list(self.candidates)
        return data


# ---------------------------------------------------------------------------
# Templates
# ---------------------------------------------------------------------------
# Cada template: (slug, literal_regex_com_{target}, "end"|"mid", family, operation)
# "end": target no FIM -> \S+ (greedy), fullmatch delimita.
# "mid": target no MEIO -> \S+? (non-greedy), seguido de texto literal.
#
# TARGET_CHARS aceita letras, digitos, '_', '.', '[', ']', '+', '-' (e
# qualquer caractere não-espaço, na prática, já que usamos \S).

_TARGET_END = r"(?P<target>\S+)"
_TARGET_MID = r"(?P<target>\S+?)"


def _end(prefix_literal: str) -> str:
    return prefix_literal + _TARGET_END


def _mid(prefix_literal: str, suffix_literal: str) -> str:
    return prefix_literal + _TARGET_MID + suffix_literal


# (slug, literal_template_with_target_placeholder, position, family, operation)
# position: "end" ou "mid". Para "mid", o template contém "{target}" entre
# prefixo e sufixo; para "end", "{target}" está ao final.

_RAW_TEMPLATES: list[tuple[str, str, str, str, str | None]] = [
    # SYMBOL
    ("find_symbol_canonical", "find symbol {target}", "end", "symbol", "find_symbol"),
    ("buscar_simbolo", "buscar símbolo {target}", "end", "symbol", "find_symbol"),
    ("localizar_simbolo", "localizar símbolo {target}", "end", "symbol", "find_symbol"),
    ("o_que_e_x", "o que é {target}", "end", "symbol", "find_symbol"),
    ("onde_esta_declarado_x", "onde está declarado {target}", "end", "symbol", "find_symbol"),
    # READS
    ("find_reads_canonical", "find reads {target}", "end", "reads", "find_reads"),
    ("buscar_leituras_de_x", "buscar leituras de {target}", "end", "reads", "find_reads"),
    ("onde_x_e_lido", "onde {target} é lido", "mid", "reads", "find_reads"),
    ("quem_le_x", "quem lê {target}", "end", "reads", "find_reads"),
    ("quais_pous_leem_x", "quais pous leem {target}", "end", "reads", "find_reads"),
    # WRITES
    ("find_writes_canonical", "find writes {target}", "end", "writes", "find_writes"),
    ("buscar_escritas_de_x", "buscar escritas de {target}", "end", "writes", "find_writes"),
    ("onde_x_e_escrito", "onde {target} é escrito", "mid", "writes", "find_writes"),
    ("quem_escreve_x", "quem escreve {target}", "end", "writes", "find_writes"),
    ("quais_pous_alteram_x", "quais pous alteram {target}", "end", "writes", "find_writes"),
    # CALLS
    ("find_calls_canonical", "find calls {target}", "end", "calls", "find_calls"),
    ("buscar_chamadas_de_x", "buscar chamadas de {target}", "end", "calls", "find_calls"),
    ("o_que_x_chama", "o que {target} chama", "mid", "calls", "find_calls"),
    ("quais_funcoes_x_chama", "quais funções {target} chama", "mid", "calls", "find_calls"),
    ("quais_chamadas_existem_em_x", "quais chamadas existem em {target}", "end", "calls", "find_calls"),
    # CALLERS
    ("find_callers_canonical", "find callers {target}", "end", "callers", "find_callers"),
    ("buscar_chamadores_de_x", "buscar chamadores de {target}", "end", "callers", "find_callers"),
    ("quem_chama_x", "quem chama {target}", "end", "callers", "find_callers"),
    ("quais_pous_chamam_x", "quais pous chamam {target}", "end", "callers", "find_callers"),
    ("onde_x_e_chamado", "onde {target} é chamado", "mid", "callers", "find_callers"),
    # AMBIGUOUS (usage)
    ("onde_x_e_usado", "onde {target} é usado", "mid", "ambiguous", None),
    ("quem_usa_x", "quem usa {target}", "end", "ambiguous", None),
    ("buscar_x_bare", "buscar {target}", "end", "ambiguous", None),
    # UNSUPPORTED (explanation/reasoning)
    ("explique_x", "explique {target}", "end", "unsupported", None),
    ("por_que_x_muda", "por que {target} muda", "mid", "unsupported", None),
    ("qual_a_logica_de_x", "qual a lógica de {target}", "end", "unsupported", None),
]


def _template_to_regex(template: str, position: str, fold: bool) -> str:
    """Constrói o regex final a partir do texto literal do template
    (substituindo '{target}' pelo grupo nomeado apropriado), escapando o
    restante do texto literal. Se `fold`, aplica accent_fold(lower()) no
    texto literal ANTES de escapar (para casar com o texto 'folded')."""
    before, _, after = template.partition("{target}")

    def _lit(s: str) -> str:
        s = s.strip()
        if fold:
            s = accent_fold(s.lower())
        # Espaços internos: colapsar para \s+ não é necessário pois o
        # `working`/`folded` já tem espaços colapsados a um único ' '.
        return re.escape(s)

    before_re = _lit(before)
    after_re = _lit(after)
    group = _TARGET_END if position == "end" else _TARGET_MID

    parts = []
    if before_re:
        parts.append(before_re + " ")
    parts.append(group)
    if after_re:
        parts.append(" " + after_re)
    return "".join(parts)


# Pré-compila as duas variantes (exata / folded) de cada template, na MESMA
# ordem global de tentativa especificada.
_COMPILED_EXACT: list[tuple[str, str, str, re.Pattern]] = []
_COMPILED_FOLDED: list[tuple[str, str, str, re.Pattern]] = []

for _slug, _tmpl, _pos, _family, _op in _RAW_TEMPLATES:
    _exact_re = _template_to_regex(_tmpl, _pos, fold=False)
    _folded_re = _template_to_regex(_tmpl, _pos, fold=True)
    _COMPILED_EXACT.append((_slug, _family, _op, re.compile(_exact_re)))
    _COMPILED_FOLDED.append((_slug, _family, _op, re.compile(_folded_re)))


_FAMILY_REASON = {
    "ambiguous": "usage_does_not_distinguish_read_from_write",
    "unsupported": "explanation_or_reasoning_question_out_of_scope",
}

# ---------------------------------------------------------------------------
# "por favor" prefix removal
# ---------------------------------------------------------------------------

_POR_FAVOR_RE = re.compile(
    r"^\s*por\s+favor\s*,?\s*", re.IGNORECASE
)


def _strip_por_favor(text: str) -> str:
    """Remove um prefixo 'por favor' (case/acento-insensível) apenas no
    INÍCIO do texto, incluindo vírgula/espaço opcionais logo após."""
    folded_lower = accent_fold(text.lower())
    match = re.match(r"^\s*por\s+favor\s*,?\s*", folded_lower)
    if match:
        # Mesmo alinhamento 1:1 (accent_fold preserva contagem de
        # caracteres) -- fatia o texto ORIGINAL no mesmo offset.
        return text[match.end() :]
    return text


_TERMINAL_PUNCT_RE = re.compile(r"[?.!;:]+$")

_TRIGGER_VERB_RE = re.compile(
    r"(find\s+symbol|find\s+reads|find\s+writes|find\s+calls|find\s+callers|"
    r"buscar\s+simbolo|buscar\s+leituras\s+de|buscar\s+escritas\s+de|"
    r"buscar\s+chamadas\s+de|buscar\s+chamadores\s+de|buscar)",
)

# Prefixos ESPECIFICOS (verbo + parte fixa do template) que, se aparecerem
# SOZINHOS (sem nenhum token residual apos o prefixo), configuram
# "missing_target" -- MESMO que o restante pudesse, em tese, casar com o
# template bare "buscar {target}" (ex.: "buscar simbolo" nao deve virar
# ambiguous com target="simbolo"). Checado ANTES do bare, no fold espaco-
# normalizado (1:1 com working).
_SPECIFIC_PREFIX_ONLY_RE = re.compile(
    r"^(buscar\s+simbolo|localizar\s+simbolo|buscar\s+leituras\s+de|"
    r"buscar\s+escritas\s+de|buscar\s+chamadas\s+de|buscar\s+chamadores\s+de)$"
)

# Pares de delimitadores reconhecidos para remoção de UM par externo.
_QUOTE_PAIRS = {
    '"': '"',
    "'": "'",
    "`": "`",
    "“": "”",  # “ ”
    "‘": "’",  # ‘ ’
}


def _strip_outer_quotes(target: str) -> str:
    if len(target) < 2:
        return target
    first, last = target[0], target[-1]
    if first in _QUOTE_PAIRS and _QUOTE_PAIRS[first] == last:
        return target[1:-1]
    return target


# ---------------------------------------------------------------------------
# parse_query_intent
# ---------------------------------------------------------------------------


def parse_query_intent(text: str | None) -> QueryIntent:
    # 1. None ou vazio (apos strip).
    if text is None:
        return QueryIntent(status="invalid", reason="empty_input", confidence="none", target=None)
    if text.strip() == "":
        return QueryIntent(status="invalid", reason="empty_input", confidence="none", target=None)

    # 2. Contagem de '?' ANTES de qualquer limpeza.
    question_mark_count = text.count("?")

    # 3. Colapsa espacos repetidos, preserva acentos/caixa/pontuacao interna.
    working = re.sub(r"\s+", " ", text).strip()

    # 4. Remove prefixo "por favor" (+ virgula/espaco opcionais), no INICIO.
    working = _strip_por_favor(working)
    working = working.strip()

    # 5. Remove pontuacao terminal (?.!;: um ou mais) do FIM.
    working = _TERMINAL_PUNCT_RE.sub("", working).strip()

    if working == "":
        # Sobrou nada apos remover prefixo/pontuacao/verbo -- trata como
        # entrada malformada equivalente a "sem target".
        return QueryIntent(status="invalid", reason="missing_target", confidence="none", target=None)

    # 7. accent_fold(lower()) alinhado 1:1 com `working`.
    folded = accent_fold(working.lower())

    # Guarda: um prefixo de verbo ESPECIFICO ("buscar simbolo", "buscar
    # leituras de", etc.) aparecendo SOZINHO (sem target algum apos) e
    # missing_target -- mesmo que o texto residual pudesse, em teoria,
    # casar com o template bare "buscar {target}" mais generico (que so e
    # tentado DEPOIS de todos os especificos, por especificacao). Sem esta
    # guarda, "buscar simbolo" cairia erroneamente em buscar_x_bare com
    # target="simbolo".
    if _SPECIFIC_PREFIX_ONLY_RE.match(folded):
        return QueryIntent(status="invalid", reason="missing_target", confidence="none", target=None)

    # 8. EXACT PASS.
    for slug, family, op, pattern in _COMPILED_EXACT:
        m = pattern.fullmatch(working)
        if m:
            return _build_intent_from_match(m, working, slug, family, op, confidence="exact")

    # 9. NORMALIZED PASS.
    for slug, family, op, pattern in _COMPILED_FOLDED:
        m = pattern.fullmatch(folded)
        if m:
            start, end = m.span("target")
            raw_target = working[start:end]
            return _finalize_intent(raw_target, slug, family, op, confidence="normalized")

    # 11. Nenhum template casou.
    if question_mark_count >= 2:
        return QueryIntent(
            status="invalid",
            reason="multiple_questions_in_single_input",
            target=None,
            confidence="none",
        )

    if _TRIGGER_VERB_RE.search(folded) is not None:
        # Verbo-gatilho presente, mas sem token restante para virar target.
        # Já tratamos "working == ''" acima; aqui cobre o caso em que o
        # verbo aparece mas nao ha mais nada alem dele (ex.: "find symbol",
        # "buscar simbolo").
        after_verb = _TRIGGER_VERB_RE.sub("", folded, count=1).strip()
        if after_verb == "":
            return QueryIntent(
                status="invalid", reason="missing_target", target=None, confidence="none"
            )

    return QueryIntent(
        status="unsupported", reason="no_recognized_pattern", target=None, confidence="none"
    )


def _build_intent_from_match(
    m: re.Match, working: str, slug: str, family: str, op: str | None, confidence: str
) -> QueryIntent:
    start, end = m.span("target")
    raw_target = working[start:end]
    return _finalize_intent(raw_target, slug, family, op, confidence)


def _finalize_intent(
    raw_target: str, slug: str, family: str, op: str | None, confidence: str
) -> QueryIntent:
    target = _strip_outer_quotes(raw_target)

    if family == "ambiguous":
        return QueryIntent(
            status="ambiguous",
            operation=None,
            target=target,
            matched_pattern=slug,
            confidence=confidence,
            reason=_FAMILY_REASON["ambiguous"],
            candidates=["find_reads", "find_writes"],
        )
    if family == "unsupported":
        return QueryIntent(
            status="unsupported",
            operation=None,
            target=target,
            matched_pattern=slug,
            confidence=confidence,
            reason=_FAMILY_REASON["unsupported"],
        )
    # 5 operacoes.
    return QueryIntent(
        status="matched",
        operation=op,
        target=target,
        matched_pattern=slug,
        confidence=confidence,
    )

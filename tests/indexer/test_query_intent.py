"""Testes de mastertool_bridge.indexer.query_intent (parser puro).

Nenhum teste aqui toca disco ou importa query.py/symbol_resolver.py -- o
modulo sob teste depende apenas de stdlib (dataclasses/re/unicodedata).
"""

from __future__ import annotations

import json

from mastertool_bridge.indexer.query_intent import accent_fold, parse_query_intent

# ---------------------------------------------------------------------------
# accent_fold: preservacao de contagem de caracteres (1:1)
# ---------------------------------------------------------------------------


def test_accent_fold_preserves_character_count_for_all_accents_used() -> None:
    accented = "áàãâéêíóôõúç"
    for ch in accented:
        folded = accent_fold(ch)
        assert len(folded) == 1, f"{ch!r} -> {folded!r} (len={len(folded)})"


def test_accent_fold_full_word_preserves_length() -> None:
    word = "símbolo é chamado política"
    folded = accent_fold(word)
    assert len(folded) == len(word)


# ---------------------------------------------------------------------------
# SYMBOL family
# ---------------------------------------------------------------------------


def test_symbol_canonical_english() -> None:
    r = parse_query_intent("find symbol Estado_OP")
    assert r.status == "matched"
    assert r.operation == "find_symbol"
    assert r.target == "Estado_OP"
    assert r.matched_pattern == "find_symbol_canonical"
    assert r.confidence == "exact"


def test_symbol_buscar_simbolo() -> None:
    r = parse_query_intent("buscar símbolo Estado_OP")
    assert r.status == "matched"
    assert r.operation == "find_symbol"
    assert r.target == "Estado_OP"
    assert r.matched_pattern == "buscar_simbolo"


def test_symbol_o_que_e() -> None:
    r = parse_query_intent("o que é Estado_OP?")
    assert r.status == "matched"
    assert r.operation == "find_symbol"
    assert r.target == "Estado_OP"
    assert r.matched_pattern == "o_que_e_x"


def test_symbol_onde_esta_declarado() -> None:
    r = parse_query_intent("onde está declarado Estado_OP")
    assert r.status == "matched"
    assert r.operation == "find_symbol"
    assert r.target == "Estado_OP"


# ---------------------------------------------------------------------------
# READS family
# ---------------------------------------------------------------------------


def test_reads_canonical_english() -> None:
    r = parse_query_intent("find reads Estado_OP")
    assert r.status == "matched"
    assert r.operation == "find_reads"
    assert r.target == "Estado_OP"


def test_reads_onde_x_e_lido() -> None:
    r = parse_query_intent("onde Estado_OP é lido?")
    assert r.status == "matched"
    assert r.operation == "find_reads"
    assert r.target == "Estado_OP"
    assert r.matched_pattern == "onde_x_e_lido"


def test_reads_quem_le() -> None:
    r = parse_query_intent("quem lê Estado_OP?")
    assert r.status == "matched"
    assert r.operation == "find_reads"
    assert r.target == "Estado_OP"


def test_reads_quais_pous_leem() -> None:
    r = parse_query_intent("quais pous leem Estado_OP?")
    assert r.status == "matched"
    assert r.operation == "find_reads"
    assert r.target == "Estado_OP"


# ---------------------------------------------------------------------------
# WRITES family
# ---------------------------------------------------------------------------


def test_writes_canonical_english() -> None:
    r = parse_query_intent("find writes Estado_OP")
    assert r.status == "matched"
    assert r.operation == "find_writes"
    assert r.target == "Estado_OP"


def test_writes_onde_x_e_escrito() -> None:
    r = parse_query_intent("onde Estado_OP é escrito?")
    assert r.status == "matched"
    assert r.operation == "find_writes"
    assert r.target == "Estado_OP"
    assert r.matched_pattern == "onde_x_e_escrito"


def test_writes_quem_escreve() -> None:
    r = parse_query_intent("quem escreve Estado_OP?")
    assert r.status == "matched"
    assert r.operation == "find_writes"
    assert r.target == "Estado_OP"


def test_writes_quais_pous_alteram() -> None:
    r = parse_query_intent("quais pous alteram Estado_OP?")
    assert r.status == "matched"
    assert r.operation == "find_writes"
    assert r.target == "Estado_OP"


# ---------------------------------------------------------------------------
# CALLS family
# ---------------------------------------------------------------------------


def test_calls_canonical_english() -> None:
    r = parse_query_intent("find calls MainPrg")
    assert r.status == "matched"
    assert r.operation == "find_calls"
    assert r.target == "MainPrg"


def test_calls_o_que_x_chama() -> None:
    r = parse_query_intent("o que MainPrg chama?")
    assert r.status == "matched"
    assert r.operation == "find_calls"
    assert r.target == "MainPrg"
    assert r.matched_pattern == "o_que_x_chama"


def test_calls_quais_funcoes_x_chama() -> None:
    r = parse_query_intent("quais funções MainPrg chama?")
    assert r.status == "matched"
    assert r.operation == "find_calls"
    assert r.target == "MainPrg"


def test_calls_quais_chamadas_existem_em() -> None:
    r = parse_query_intent("quais chamadas existem em MainPrg?")
    assert r.status == "matched"
    assert r.operation == "find_calls"
    assert r.target == "MainPrg"


# ---------------------------------------------------------------------------
# CALLERS family
# ---------------------------------------------------------------------------


def test_callers_canonical_english() -> None:
    r = parse_query_intent("find callers MainPrg")
    assert r.status == "matched"
    assert r.operation == "find_callers"
    assert r.target == "MainPrg"


def test_callers_quem_chama() -> None:
    r = parse_query_intent("quem chama MainPrg?")
    assert r.status == "matched"
    assert r.operation == "find_callers"
    assert r.target == "MainPrg"
    assert r.matched_pattern == "quem_chama_x"


def test_callers_quais_pous_chamam() -> None:
    r = parse_query_intent("quais pous chamam MainPrg?")
    assert r.status == "matched"
    assert r.operation == "find_callers"
    assert r.target == "MainPrg"


def test_callers_onde_x_e_chamado() -> None:
    r = parse_query_intent("onde MainPrg é chamado?")
    assert r.status == "matched"
    assert r.operation == "find_callers"
    assert r.target == "MainPrg"
    assert r.matched_pattern == "onde_x_e_chamado"


# ---------------------------------------------------------------------------
# target shapes: simples, pontuado, com indice
# ---------------------------------------------------------------------------


def test_target_simple_identifier() -> None:
    r = parse_query_intent("find symbol Estado_OP")
    assert r.target == "Estado_OP"


def test_target_dotted_name() -> None:
    r = parse_query_intent("find reads VarEquipamentosExemplo.MT01.RetornoDisjuntor")
    assert r.status == "matched"
    assert r.target == "VarEquipamentosExemplo.MT01.RetornoDisjuntor"


def test_target_indexed_name() -> None:
    r = parse_query_intent("find symbol GVL_A.ArrayInstancias[i].Estado")
    assert r.status == "matched"
    assert r.target == "GVL_A.ArrayInstancias[i].Estado"


# ---------------------------------------------------------------------------
# quotes stripping (aspas retas e curvas)
# ---------------------------------------------------------------------------


def test_target_straight_double_quotes_stripped() -> None:
    r = parse_query_intent('find symbol "Estado_OP"')
    assert r.target == "Estado_OP"


def test_target_straight_single_quotes_stripped() -> None:
    r = parse_query_intent("find symbol 'Estado_OP'")
    assert r.target == "Estado_OP"


def test_target_curly_double_quotes_stripped() -> None:
    r = parse_query_intent("find symbol “Estado_OP”")
    assert r.target == "Estado_OP"


def test_target_curly_single_quotes_stripped() -> None:
    r = parse_query_intent("find symbol ‘Estado_OP’")
    assert r.target == "Estado_OP"


def test_target_quotes_preserve_internal_content() -> None:
    r = parse_query_intent('find symbol "VarEquipamentosExemplo.MT01.RetornoDisjuntor"')
    assert r.target == "VarEquipamentosExemplo.MT01.RetornoDisjuntor"


# ---------------------------------------------------------------------------
# exact vs normalized confidence (mesmo template, com/sem acentos, caixa)
# ---------------------------------------------------------------------------


def test_confidence_exact_with_correct_accents() -> None:
    r = parse_query_intent("buscar símbolo Estado_OP")
    assert r.confidence == "exact"
    assert r.matched_pattern == "buscar_simbolo"
    assert r.status == "matched"


def test_confidence_normalized_without_accents() -> None:
    r = parse_query_intent("buscar simbolo Estado_OP")
    assert r.confidence == "normalized"
    assert r.matched_pattern == "buscar_simbolo"
    assert r.status == "matched"
    assert r.target == "Estado_OP"


def test_confidence_normalized_different_case() -> None:
    r = parse_query_intent("BUSCAR SÍMBOLO Estado_OP")
    assert r.confidence == "normalized"
    assert r.target == "Estado_OP"  # caixa original do target preservada


# ---------------------------------------------------------------------------
# pontuacao terminal variada
# ---------------------------------------------------------------------------


def test_terminal_punctuation_question_mark() -> None:
    r = parse_query_intent("onde Estado_OP é escrito?")
    assert r.status == "matched"
    assert r.target == "Estado_OP"


def test_terminal_punctuation_period() -> None:
    r = parse_query_intent("find symbol Estado_OP.")
    assert r.status == "matched"
    assert r.target == "Estado_OP"


def test_terminal_punctuation_exclamation() -> None:
    r = parse_query_intent("find symbol Estado_OP!")
    assert r.status == "matched"
    assert r.target == "Estado_OP"


def test_terminal_punctuation_semicolon() -> None:
    r = parse_query_intent("find symbol Estado_OP;")
    assert r.status == "matched"
    assert r.target == "Estado_OP"


def test_terminal_punctuation_combination() -> None:
    r = parse_query_intent("find symbol Estado_OP?!")
    assert r.status == "matched"
    assert r.target == "Estado_OP"


# ---------------------------------------------------------------------------
# "por favor" prefix
# ---------------------------------------------------------------------------


def test_por_favor_prefix_removed() -> None:
    r = parse_query_intent("por favor, buscar símbolo Estado_OP")
    assert r.status == "matched"
    assert r.target == "Estado_OP"
    assert r.matched_pattern == "buscar_simbolo"


def test_por_favor_prefix_without_comma() -> None:
    r = parse_query_intent("por favor find symbol Estado_OP")
    assert r.status == "matched"
    assert r.target == "Estado_OP"


# ---------------------------------------------------------------------------
# ambiguous (usage) family: 3 variantes
# ---------------------------------------------------------------------------


def test_ambiguous_onde_x_e_usado() -> None:
    r = parse_query_intent("onde Estado_OP é usado?")
    assert r.status == "ambiguous"
    assert r.candidates == ["find_reads", "find_writes"]
    assert r.target == "Estado_OP"
    assert r.reason == "usage_does_not_distinguish_read_from_write"


def test_ambiguous_quem_usa() -> None:
    r = parse_query_intent("quem usa Estado_OP?")
    assert r.status == "ambiguous"
    assert r.candidates == ["find_reads", "find_writes"]
    assert r.target == "Estado_OP"


def test_ambiguous_buscar_bare() -> None:
    r = parse_query_intent("buscar Estado_OP")
    assert r.status == "ambiguous"
    assert r.candidates == ["find_reads", "find_writes"]
    assert r.target == "Estado_OP"
    assert r.matched_pattern == "buscar_x_bare"


# ---------------------------------------------------------------------------
# unsupported family: 3 variantes
# ---------------------------------------------------------------------------


def test_unsupported_explique() -> None:
    r = parse_query_intent("explique Estado_OP")
    assert r.status == "unsupported"
    assert r.operation is None
    assert r.target == "Estado_OP"
    assert r.reason == "explanation_or_reasoning_question_out_of_scope"


def test_unsupported_por_que_muda() -> None:
    r = parse_query_intent("por que Estado_OP muda?")
    assert r.status == "unsupported"
    assert r.target == "Estado_OP"


def test_unsupported_qual_a_logica() -> None:
    r = parse_query_intent("qual a lógica de Estado_OP?")
    assert r.status == "unsupported"
    assert r.target == "Estado_OP"


def test_unsupported_no_recognized_pattern_fallback() -> None:
    r = parse_query_intent("blah blah nothing recognized here")
    assert r.status == "unsupported"
    assert r.reason == "no_recognized_pattern"
    assert r.target is None


# ---------------------------------------------------------------------------
# missing target -> invalid
# ---------------------------------------------------------------------------


def test_missing_target_find_symbol_alone() -> None:
    r = parse_query_intent("find symbol")
    assert r.status == "invalid"
    assert r.reason == "missing_target"
    assert r.target is None


def test_missing_target_buscar_simbolo_alone() -> None:
    r = parse_query_intent("buscar símbolo")
    assert r.status == "invalid"
    assert r.reason == "missing_target"
    assert r.target is None


def test_missing_target_bare_buscar_alone() -> None:
    r = parse_query_intent("buscar")
    assert r.status == "invalid"
    assert r.reason == "missing_target"


def test_missing_target_never_falls_into_bare_ambiguous_regression() -> None:
    """Regressao explicita: 'buscar simbolo' (verbo especifico + sem
    target) NUNCA deve degradar para o template bare 'buscar {target}'
    tratando 'simbolo' como target."""
    r = parse_query_intent("buscar símbolo")
    assert r.status != "ambiguous"
    assert r.matched_pattern != "buscar_x_bare"
    assert r.status == "invalid"


# ---------------------------------------------------------------------------
# duas perguntas coladas -> invalid
# ---------------------------------------------------------------------------


def test_two_questions_glued_find_symbol_and_find_reads() -> None:
    r = parse_query_intent("find symbol X? find reads Y?")
    assert r.status == "invalid"
    assert r.reason == "multiple_questions_in_single_input"
    assert r.target is None


def test_two_questions_glued_onde_lido_onde_escrito() -> None:
    r = parse_query_intent("onde X é lido? onde Y é escrito?")
    assert r.status == "invalid"
    assert r.reason == "multiple_questions_in_single_input"


# ---------------------------------------------------------------------------
# malformado -> invalid
# ---------------------------------------------------------------------------


def test_malformed_empty_string() -> None:
    r = parse_query_intent("")
    assert r.status == "invalid"
    assert r.reason == "empty_input"


def test_malformed_whitespace_only() -> None:
    r = parse_query_intent("   ")
    assert r.status == "invalid"
    assert r.reason == "empty_input"


def test_malformed_punctuation_only() -> None:
    r = parse_query_intent("???")
    assert r.status == "invalid"


def test_malformed_none() -> None:
    r = parse_query_intent(None)
    assert r.status == "invalid"
    assert r.reason == "empty_input"


# ---------------------------------------------------------------------------
# regression: buscar simbolo NUNCA cai no template bare ambiguous
# ---------------------------------------------------------------------------


def test_buscar_simbolo_with_target_never_ambiguous() -> None:
    r = parse_query_intent("buscar símbolo Estado_OP")
    assert r.status == "matched"
    assert r.operation == "find_symbol"
    assert r.matched_pattern == "buscar_simbolo"


# ---------------------------------------------------------------------------
# to_dict / determinismo
# ---------------------------------------------------------------------------


def test_to_dict_stable_json_output() -> None:
    r1 = parse_query_intent("find symbol Estado_OP")
    r2 = parse_query_intent("find symbol Estado_OP")
    json1 = json.dumps(r1.to_dict(), indent=2, ensure_ascii=False, sort_keys=True)
    json2 = json.dumps(r2.to_dict(), indent=2, ensure_ascii=False, sort_keys=True)
    assert json1 == json2


def test_to_dict_contains_expected_keys_when_matched() -> None:
    r = parse_query_intent("find symbol Estado_OP")
    d = r.to_dict()
    assert d["status"] == "matched"
    assert d["operation"] == "find_symbol"
    assert d["target"] == "Estado_OP"
    assert d["matched_pattern"] == "find_symbol_canonical"
    assert d["confidence"] == "exact"
    assert "reason" not in d
    assert "candidates" not in d


def test_to_dict_contains_candidates_when_ambiguous() -> None:
    r = parse_query_intent("buscar Estado_OP")
    d = r.to_dict()
    assert d["candidates"] == ["find_reads", "find_writes"]
    assert d["reason"] == "usage_does_not_distinguish_read_from_write"

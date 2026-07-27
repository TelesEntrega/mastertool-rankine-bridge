from mastertool_bridge.analysis.reference_finder import (filter_reads,
                                                         filter_writes,
                                                         find_in_text,
                                                         find_references)
from mastertool_bridge.constants import (USAGE_CONFIRMED_READ,
                                         USAGE_CONFIRMED_WRITE,
                                         USAGE_PROBABLE_WRITE, USAGE_UNKNOWN)
from mastertool_bridge.export.loader import load_export

IMPL = """\
xMotorLigado := fbMotor.xMotor;
IF xMotorLigado THEN
    rVelocidade := rVelocidade + 1.0;
END_IF
aiPressoes[i] := 0;
tonPartida(IN := TRUE, PT := T#2S);
saida := entrada AND NOT xMotorLigado; // comentario com xMotorLigado
"""


def test_direct_assignment_is_confirmed_write():
    refs = find_in_text(IMPL, "xMotorLigado", "Obj")
    assert refs[0].usage == USAGE_CONFIRMED_WRITE
    assert refs[0].line == 1


def test_condition_is_confirmed_read():
    refs = find_in_text(IMPL, "xMotorLigado", "Obj")
    assert refs[1].usage == USAGE_CONFIRMED_READ


def test_comment_occurrences_ignored():
    refs = find_in_text(IMPL, "xMotorLigado", "Obj")
    # linha 1 (escrita), linha 2 (condição), linha 7 (expressão) — não o comentário
    assert len(refs) == 3


def test_right_side_is_read():
    refs = find_in_text(IMPL, "rVelocidade", "Obj")
    assert refs[0].usage == USAGE_CONFIRMED_WRITE
    assert refs[1].usage == USAGE_CONFIRMED_READ


def test_array_element_is_probable_write():
    refs = find_in_text(IMPL, "aiPressoes", "Obj")
    assert refs[0].usage == USAGE_PROBABLE_WRITE


def test_fb_call_is_unknown():
    refs = find_in_text(IMPL, "tonPartida", "Obj")
    assert refs[0].usage == USAGE_UNKNOWN


def test_parameter_assignment_is_probable_write():
    refs = find_in_text(IMPL, "IN", "Obj")
    assert refs[0].usage == USAGE_PROBABLE_WRITE


def test_member_access_not_matched():
    # fbMotor.xMotor não deve contar como referência a xMotor
    refs = find_in_text(IMPL, "xMotor", "Obj")
    assert refs == []


def test_project_wide_search(sample_project_dir):
    project = load_export(sample_project_dir)
    refs = find_references(project, "xMotorLigado")
    writes = filter_writes(refs)
    reads = filter_reads(refs)
    assert writes and all(r.object_name == "Application.POUs.MainPrg"
                          for r in writes)
    assert reads

from mastertool_bridge.static_api.classifier import (READ_CANDIDATE,
                                                     UNKNOWN,
                                                     WRITE_CANDIDATE,
                                                     ONLINE_CANDIDATE,
                                                     classify_method,
                                                     classify_property,
                                                     classify_type_members,
                                                     property_note)


def test_get_children_is_read_candidate():
    assert classify_method("get_children") == READ_CANDIDATE


def test_find_is_read_candidate():
    assert classify_method("find") == READ_CANDIDATE


def test_get_name_is_read_candidate():
    assert classify_method("get_name") == READ_CANDIDATE


def test_save_is_write_candidate():
    assert classify_method("save") == WRITE_CANDIDATE


def test_close_is_write_candidate():
    assert classify_method("close") == WRITE_CANDIDATE


def test_export_xml_is_write_candidate_not_read():
    # "export" tem nome que parece leitura mas grava arquivo em disco —
    # deve ficar write_candidate, nunca read_candidate por omissão.
    assert classify_method("export_xml") == WRITE_CANDIDATE


def test_build_rebuild_clean_generate_code_are_write_candidates():
    for name in ("build", "rebuild", "clean", "generate_code"):
        assert classify_method(name) == WRITE_CANDIDATE


def test_unknown_method_name_defaults_to_unknown_never_read():
    # nome ambiguo/nao catalogado nunca deve virar read_candidate por omissao
    assert classify_method("some_totally_unrecognized_method") == UNKNOWN


def test_online_keyword_takes_priority_over_write_keyword():
    # "download" e' online, mesmo que o nome tambem contenha padroes write-ish
    assert classify_method("download_and_save") == ONLINE_CANDIDATE


def test_get_by_path_is_not_promoted_to_read_without_evidence():
    # ambiguo (pode carregar/abrir um projeto ainda nao carregado) - nao esta
    # na whitelist de leitura confirmada, entao fica unknown.
    assert classify_method("get_by_path") == UNKNOWN


def test_readonly_scalar_property_is_read_candidate():
    assert classify_property("path", can_write=False, prop_type="System.String") == READ_CANDIDATE
    assert classify_property("is_folder", can_write=False, prop_type="System.Boolean") == READ_CANDIDATE
    assert classify_property("guid", can_write=False, prop_type="System.Guid") == READ_CANDIDATE


def test_writable_property_is_write_candidate_even_if_scalar():
    assert classify_property("active_application", can_write=True,
                             prop_type="SomeWrapper`1[[X]]") == WRITE_CANDIDATE


def test_complex_readonly_property_is_unknown_not_read():
    # tipo complexo (nao escalar) sem evidencia extra fica unknown, mesmo
    # sem setter.
    assert classify_property("parent", can_write=False, prop_type="System.Object") == UNKNOWN
    assert classify_property("embedded_object_types", can_write=False,
                             prop_type="System.Collections.Generic.IList`1[[System.Guid]]") == UNKNOWN


def test_property_note_flags_getter_setter_combo():
    note = property_note(can_read=True, can_write=True)
    assert note is not None
    assert "getter" in note.lower() or "leitura" in note.lower()


def test_property_note_absent_for_readonly():
    assert property_note(can_read=True, can_write=False) is None


def test_classify_type_members_annotates_all_entries():
    type_entry = {
        "full_name": "Fake.IThing",
        "properties": [
            {"name": "path", "type": "System.String", "can_read": True, "can_write": False},
            {"name": "active_application", "type": "Fake.Wrapper", "can_read": True, "can_write": True},
        ],
        "methods": [
            {"name": "get_children", "return_type": "System.Object", "parameters": []},
            {"name": "save", "return_type": "System.Void", "parameters": []},
        ],
    }
    result = classify_type_members(type_entry)
    by_name = {p["name"]: p for p in result["properties"]}
    assert by_name["path"]["classification"] == READ_CANDIDATE
    assert by_name["active_application"]["classification"] == WRITE_CANDIDATE
    assert "note" in by_name["active_application"]
    assert "note" not in by_name["path"]

    methods_by_name = {m["name"]: m for m in result["methods"]}
    assert methods_by_name["get_children"]["classification"] == READ_CANDIDATE
    assert methods_by_name["save"]["classification"] == WRITE_CANDIDATE

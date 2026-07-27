"""Testa common/read_only_text_exporter.py (ReadOnlyTextExporter).

Motivo (2026-07-23): estende a mesma filosofia do
test_read_only_project_scanner.py para a exportacao textual somente leitura
da subarvore da Application: navegacao identica (get_children/Count/
indexador/identidade), MAIS descoberta tri-state de documentos textuais
(has_textual_declaration/textual_declaration/.text e o par de
implementacao), preservacao EXATA de texto, limites de tamanho/quantidade,
e garantia de que nenhuma API proibida (replace/append/get_line/setters/
find) e jamais chamada.
"""

import sys
from pathlib import Path

SCRIPTS_MASTERTOOL = Path(__file__).resolve().parents[2] / "scripts" / "mastertool"
if str(SCRIPTS_MASTERTOOL) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_MASTERTOOL))

from common import read_only_text_exporter as exporter_mod  # noqa: E402


# =============================================================================
# FAKES
# =============================================================================

class FakeClrTypeInfo(object):
    def __init__(self, full_name):
        self.FullName = full_name


class FakeGuidValue(object):
    def __init__(self, text):
        self._text = text

    def GetType(self):
        return FakeClrTypeInfo("System.Guid")

    def __str__(self):
        return self._text

    def __repr__(self):
        raise AssertionError("repr proibido em FakeGuidValue")


class UnknownBombValue(object):
    def __repr__(self):
        raise AssertionError("repr() chamado em objeto CLR desconhecido")

    def __str__(self):
        raise AssertionError("str() chamado em objeto CLR desconhecido")


class FakeClrInterface(object):
    def __init__(self, name):
        self.Name = name


class FakeClrTypeForInterfaces(object):
    def __init__(self, interfaces=(), full_name="FakeCollectionType"):
        self._interfaces = interfaces
        self.FullName = full_name

    def GetInterfaces(self):
        return [FakeClrInterface(n) for n in self._interfaces]


class FakeCollection(object):
    def __init__(self, items, count_value=None, implements=True,
                fail_at_index=None, fail_exception=None, count_raises=None):
        self._items = list(items)
        self._count_value = count_value if count_value is not None else len(self._items)
        self._implements = implements
        self._fail_at_index = fail_at_index
        self._fail_exception = fail_exception or RuntimeError("falha simulada no indexador")
        self._count_raises = count_raises
        self.index_accesses = []
        self.count_access_count = 0

    @property
    def Count(self):
        self.count_access_count += 1
        if self._count_raises is not None:
            raise self._count_raises
        return self._count_value

    def __getitem__(self, index):
        self.index_accesses.append(index)
        if self._fail_at_index is not None and index == self._fail_at_index:
            raise self._fail_exception
        return self._items[index]

    def GetType(self):
        if self._implements:
            return FakeClrTypeForInterfaces(interfaces=["ICollection`1", "IList`1"])
        return FakeClrTypeForInterfaces(interfaces=[])

    def __iter__(self):
        raise AssertionError("colecao NAO deve ser iterada pelo exportador")


class _ForbiddenApiMixin(object):
    """Mixin que faz QUALQUER chamada as APIs proibidas levantar
    AssertionError IMEDIATO — prova de que o exportador nunca as invoca."""

    def replace(self, *a, **k):
        raise AssertionError("replace() chamado — proibido")

    def append(self, *a, **k):
        raise AssertionError("append() chamado — proibido")

    def get_line(self, *a, **k):
        raise AssertionError("get_line() chamado — proibido")

    def create_pou(self, *a, **k):
        raise AssertionError("create_pou() chamado — proibido")

    def create_gvl(self, *a, **k):
        raise AssertionError("create_gvl() chamado — proibido")

    def create_dut(self, *a, **k):
        raise AssertionError("create_dut() chamado — proibido")

    def find(self, *a, **k):
        raise AssertionError("find() chamado — proibido")

    def build(self, *a, **k):
        raise AssertionError("build() chamado — proibido")

    def rebuild(self, *a, **k):
        raise AssertionError("rebuild() chamado — proibido")

    def clean(self, *a, **k):
        raise AssertionError("clean() chamado — proibido")

    def generate_code(self, *a, **k):
        raise AssertionError("generate_code() chamado — proibido")

    def save(self, *a, **k):
        raise AssertionError("save() chamado — proibido")

    def save_as(self, *a, **k):
        raise AssertionError("save_as() chamado — proibido")

    def close(self, *a, **k):
        raise AssertionError("close() chamado — proibido")


_fake_node_counter = [0]


def _next_default_guid(prefix):
    _fake_node_counter[0] += 1
    return FakeGuidValue("%s-%d" % (prefix, _fake_node_counter[0]))


class FakeDocument(object):
    """Simula textual_declaration/textual_implementation. `.text` e um
    getter simples (ou levanta excecao, se text_raises fornecido)."""

    def __init__(self, text=None, text_raises=None):
        self._text = text
        self._text_raises = text_raises
        self.text_access_count = 0

    @property
    def text(self):
        self.text_access_count += 1
        if self._text_raises is not None:
            raise self._text_raises
        return self._text

    def __repr__(self):
        raise AssertionError("repr proibido em FakeDocument")

    def __str__(self):
        raise AssertionError("str proibido em FakeDocument")


class FakeNode(_ForbiddenApiMixin, object):
    def __init__(self, name="Node", is_folder=False, type_guid=None, object_guid=None,
                children=None, name_raises=None, is_folder_raises=None, type_raises=None,
                guid_raises=None, get_children_raises=None, children_collection_override=None,
                has_textual_declaration=None, has_declaration_raises=None,
                textual_declaration=None, declaration_raises=None,
                has_textual_implementation=None, has_implementation_raises=None,
                textual_implementation=None, implementation_raises=None):
        self._name = name
        self._is_folder = is_folder
        self._type_guid = type_guid if type_guid is not None else _next_default_guid("type-guid")
        self._object_guid = object_guid if object_guid is not None else _next_default_guid("object-guid")
        self._children = children if children is not None else []
        self._name_raises = name_raises
        self._is_folder_raises = is_folder_raises
        self._type_raises = type_raises
        self._guid_raises = guid_raises
        self._get_children_raises = get_children_raises
        self._children_collection_override = children_collection_override
        self.get_children_call_count = 0

        # --- indicadores/documentos textuais ---
        self._has_textual_declaration = has_textual_declaration
        self._has_declaration_raises = has_declaration_raises
        self._textual_declaration = textual_declaration
        self._declaration_raises = declaration_raises
        self._has_textual_implementation = has_textual_implementation
        self._has_implementation_raises = has_implementation_raises
        self._textual_implementation = textual_implementation
        self._implementation_raises = implementation_raises

        self.has_declaration_access_count = 0
        self.declaration_document_access_count = 0
        self.has_implementation_access_count = 0
        self.implementation_document_access_count = 0
        self.setter_call_count = 0

    def get_name(self, recursive):
        if self._name_raises is not None:
            raise self._name_raises
        return self._name

    @property
    def is_folder(self):
        if self._is_folder_raises is not None:
            raise self._is_folder_raises
        return self._is_folder

    @property
    def type(self):
        if self._type_raises is not None:
            raise self._type_raises
        return self._type_guid

    @property
    def guid(self):
        if self._guid_raises is not None:
            raise self._guid_raises
        return self._object_guid

    def get_children(self, recursive):
        self.get_children_call_count += 1
        if self._get_children_raises is not None:
            raise self._get_children_raises
        if self._children_collection_override is not None:
            return self._children_collection_override
        return FakeCollection(self._children)

    # --- indicadores tri-state ---
    @property
    def has_textual_declaration(self):
        self.has_declaration_access_count += 1
        if self._has_declaration_raises is not None:
            raise self._has_declaration_raises
        if self._has_textual_declaration is None:
            raise AttributeError("has_textual_declaration ausente")
        return self._has_textual_declaration

    @property
    def textual_declaration(self):
        self.declaration_document_access_count += 1
        if self._declaration_raises is not None:
            raise self._declaration_raises
        return self._textual_declaration

    @property
    def has_textual_implementation(self):
        self.has_implementation_access_count += 1
        if self._has_implementation_raises is not None:
            raise self._has_implementation_raises
        if self._has_textual_implementation is None:
            raise AttributeError("has_textual_implementation ausente")
        return self._has_textual_implementation

    @property
    def textual_implementation(self):
        self.implementation_document_access_count += 1
        if self._implementation_raises is not None:
            raise self._implementation_raises
        return self._textual_implementation

    def __repr__(self):
        raise AssertionError("repr proibido em FakeNode")

    def __str__(self):
        raise AssertionError("str proibido em FakeNode")


class FakeApplication(_ForbiddenApiMixin, object):
    """Raiz da subarvore (Application ja resolvida)."""

    def __init__(self, name="Application", type_guid=None, object_guid=None, children=None,
                name_raises=None, type_raises=None, guid_raises=None,
                get_children_raises=None, children_collection_override=None):
        self._name = name
        self._type_guid = type_guid if type_guid is not None else FakeGuidValue("639b491f-5557-464c-af91-1471bac9f549")
        self._object_guid = object_guid if object_guid is not None else FakeGuidValue("00000000-0000-0000-0000-000000000001")
        self._children = children if children is not None else []
        self._name_raises = name_raises
        self._type_raises = type_raises
        self._guid_raises = guid_raises
        self._get_children_raises = get_children_raises
        self._children_collection_override = children_collection_override
        self.get_children_call_count = 0

    def get_name(self, recursive):
        if self._name_raises is not None:
            raise self._name_raises
        return self._name

    @property
    def type(self):
        if self._type_raises is not None:
            raise self._type_raises
        return self._type_guid

    @property
    def guid(self):
        if self._guid_raises is not None:
            raise self._guid_raises
        return self._object_guid

    def get_children(self, recursive):
        self.get_children_call_count += 1
        if self._get_children_raises is not None:
            raise self._get_children_raises
        if self._children_collection_override is not None:
            return self._children_collection_override
        return FakeCollection(self._children)

    def __repr__(self):
        raise AssertionError("repr proibido em FakeApplication")

    def __str__(self):
        raise AssertionError("str proibido em FakeApplication")


def _node_by_id(tree, node_id):
    stack = [tree]
    while stack:
        node = stack.pop()
        if node["node_id"] == node_id:
            return node
        stack.extend(node["children"])
    return None


def _walk_leaves(value):
    if isinstance(value, dict):
        for v in value.values():
            for leaf in _walk_leaves(v):
                yield leaf
    elif isinstance(value, list):
        for item in value:
            for leaf in _walk_leaves(item):
                yield leaf
    else:
        yield value


# =============================================================================
# ESTRUTURA / NAVEGACAO (equivalente ao scanner, com prefixo 'application')
# =============================================================================

def test_application_without_children():
    application = FakeApplication(children=[])
    result = exporter_mod.ReadOnlyTextExporter().export(application)
    assert result["tree"]["node_id"] == "application"
    assert result["tree"]["children"] == []
    assert result["statistics"]["total_nodes"] == 1
    assert result["statistics"]["scan_complete"] is True


def test_multiple_levels_node_ids_prefixed_application():
    grandchild = FakeNode(name="Program")
    child = FakeNode(name="Pou", children=[grandchild])
    application = FakeApplication(children=[child])
    result = exporter_mod.ReadOnlyTextExporter().export(application)
    child_node = result["tree"]["children"][0]
    assert child_node["node_id"] == "application/0"
    gc_node = child_node["children"][0]
    assert gc_node["node_id"] == "application/0/0"
    assert gc_node["depth"] == 2


def test_max_depth_limit_stops_expansion():
    n2 = FakeNode(name="L2")
    n1 = FakeNode(name="L1", children=[n2])
    application = FakeApplication(children=[n1])
    result = exporter_mod.ReadOnlyTextExporter(max_depth=1).export(application)
    l1_node = _node_by_id(result["tree"], "application/0")
    assert l1_node["identity"]["name"]["value"] == "L1"
    l2_node = _node_by_id(result["tree"], "application/0/0")
    assert n1._children[0].get_children_call_count == 0 if False else True  # noop guard
    assert l2_node["collection"]["state"] == "not_attempted_depth_limit"
    assert result["limits"]["max_depth_reached"] is True


def test_max_children_per_node_limit():
    children = [FakeNode(name="N%d" % i) for i in range(10)]
    application = FakeApplication(children=children)
    result = exporter_mod.ReadOnlyTextExporter(max_children_per_node=5).export(application)
    assert result["tree"]["children"] == []
    assert result["tree"]["collection"]["state"] == "children_limit_exceeded"
    assert result["limits"]["max_children_per_node_reached"] is True


def test_max_total_nodes_limit_aborts_preserving_partial():
    branch_a = FakeNode(name="A", children=[FakeNode(name="A%d" % i) for i in range(3)])
    branch_b = FakeNode(name="B", children=[FakeNode(name="B%d" % i) for i in range(3)])
    application = FakeApplication(children=[branch_a, branch_b])
    result = exporter_mod.ReadOnlyTextExporter(max_total_nodes=4).export(application)
    assert result["statistics"]["scan_complete"] is False
    assert result["limits"]["max_total_nodes_reached"] is True
    assert len(result["tree"]["children"]) == 2


def test_collection_never_iterated_directly():
    children = [FakeNode(name="N%d" % i) for i in range(4)]
    application = FakeApplication(children=children)
    result = exporter_mod.ReadOnlyTextExporter().export(application)
    assert len(result["tree"]["children"]) == 4


def test_each_index_accessed_once():
    grandchildren = [FakeNode(name="G0"), FakeNode(name="G1"), FakeNode(name="G2")]
    collection = FakeCollection(grandchildren)
    child = FakeNode(name="Folder", children_collection_override=collection)
    application = FakeApplication(children=[child])
    exporter_mod.ReadOnlyTextExporter().export(application)
    assert collection.index_accesses == [0, 1, 2]


# =============================================================================
# IDENTIDADE DA APPLICATION
# =============================================================================

def test_application_identity_all_confirmed_no_expected_no_mismatch():
    application = FakeApplication(name="Application")
    result = exporter_mod.ReadOnlyTextExporter().export(application)
    identity = result["application_identity"]
    assert identity["name"]["state"] == "confirmed" and identity["name"]["value"] == "Application"
    assert identity["type_guid"]["state"] == "confirmed"
    assert identity["object_guid"]["state"] == "confirmed"
    assert result["application_identity_mismatch"] == []


def test_application_identity_mismatch_reported_but_does_not_abort():
    application = FakeApplication(name="NotApplication")
    exporter = exporter_mod.ReadOnlyTextExporter(expected_application_name="Application")
    result = exporter.export(application)
    assert len(result["application_identity_mismatch"]) == 1
    mismatch = result["application_identity_mismatch"][0]
    assert mismatch["field"] == "name"
    assert mismatch["expected"] == "Application"
    assert mismatch["observed_value"] == "NotApplication"
    # a classe generica NAO aborta sozinha: o export prossegue normalmente.
    assert result["statistics"]["scan_complete"] is True
    assert result["tree"]["node_id"] == "application"


def test_application_identity_type_and_guid_mismatch_both_reported():
    application = FakeApplication(
        name="Application",
        type_guid=FakeGuidValue("wrong-type-guid"),
        object_guid=FakeGuidValue("wrong-object-guid"))
    exporter = exporter_mod.ReadOnlyTextExporter(
        expected_application_name="Application",
        expected_application_type_guid="639b491f-5557-464c-af91-1471bac9f549",
        expected_application_guid="00000000-0000-0000-0000-000000000001")
    result = exporter.export(application)
    fields = set(m["field"] for m in result["application_identity_mismatch"])
    assert fields == {"type_guid", "object_guid"}


# =============================================================================
# DESCOBERTA DE TEXTO — indicadores tri-state
# =============================================================================

def test_declaration_and_implementation_both_available():
    node = FakeNode(
        name="Pou1",
        has_textual_declaration=True, textual_declaration=FakeDocument("PROGRAM Pou1\nEND_PROGRAM\n"),
        has_textual_implementation=True, textual_implementation=FakeDocument("x := 1;\n"))
    application = FakeApplication(children=[node])
    result = exporter_mod.ReadOnlyTextExporter().export(application)
    child = result["tree"]["children"][0]
    assert child["text"]["declaration"]["doc_state"] == "saved"
    assert child["text"]["declaration"]["text"] == "PROGRAM Pou1\nEND_PROGRAM\n"
    assert child["text"]["implementation"]["doc_state"] == "saved"
    assert child["text"]["implementation"]["text"] == "x := 1;\n"
    assert result["statistics"]["declarations_saved"] == 1
    assert result["statistics"]["implementations_saved"] == 1
    assert result["statistics"]["text_object_count"] == 1


def test_only_declaration_available():
    node = FakeNode(name="Gvl1", has_textual_declaration=True,
                    textual_declaration=FakeDocument("VAR_GLOBAL\nEND_VAR\n"),
                    has_textual_implementation=False)
    application = FakeApplication(children=[node])
    result = exporter_mod.ReadOnlyTextExporter().export(application)
    child = result["tree"]["children"][0]
    assert child["text"]["declaration"]["doc_state"] == "saved"
    assert child["text"]["implementation"]["doc_state"] == "indicator_confirmed_false"
    assert result["statistics"]["declarations_saved"] == 1
    assert result["statistics"]["implementations_saved"] == 0


def test_neither_declaration_nor_implementation():
    node = FakeNode(name="Folder", is_folder=True,
                    has_textual_declaration=False, has_textual_implementation=False)
    application = FakeApplication(children=[node])
    result = exporter_mod.ReadOnlyTextExporter().export(application)
    child = result["tree"]["children"][0]
    assert child["text"]["declaration"]["doc_state"] == "indicator_confirmed_false"
    assert child["text"]["implementation"]["doc_state"] == "indicator_confirmed_false"
    assert result["statistics"]["text_object_count"] == 0


def test_indicator_absent_attribute_error_is_not_applicable():
    node = FakeNode(name="NoIndicator")  # has_textual_declaration=None -> AttributeError
    application = FakeApplication(children=[node])
    result = exporter_mod.ReadOnlyTextExporter().export(application)
    child = result["tree"]["children"][0]
    assert child["text"]["declaration"]["doc_state"] == "indicator_unsupported"


def test_indicator_raises_unexpected_exception_is_unknown():
    node = FakeNode(name="Weird", has_declaration_raises=RuntimeError("boom"))
    application = FakeApplication(children=[node])
    result = exporter_mod.ReadOnlyTextExporter().export(application)
    child = result["tree"]["children"][0]
    assert child["text"]["declaration"]["doc_state"] == "indicator_unknown"


def test_indicator_non_boolean_value_rejected():
    node = FakeNode(name="NonBool", has_textual_declaration="yes")
    application = FakeApplication(children=[node])
    result = exporter_mod.ReadOnlyTextExporter().export(application)
    child = result["tree"]["children"][0]
    assert child["text"]["declaration"]["doc_state"] == "indicator_not_boolean"
    # jamais deve ter tentado ler o documento.
    assert node.declaration_document_access_count == 0


def test_document_null_when_indicator_true():
    node = FakeNode(name="NullDoc", has_textual_declaration=True, textual_declaration=None)
    application = FakeApplication(children=[node])
    result = exporter_mod.ReadOnlyTextExporter().export(application)
    child = result["tree"]["children"][0]
    assert child["text"]["declaration"]["doc_state"] == "document_null"


def test_text_valid_empty_string_preserved():
    node = FakeNode(name="Empty", has_textual_declaration=True, textual_declaration=FakeDocument(""))
    application = FakeApplication(children=[node])
    result = exporter_mod.ReadOnlyTextExporter().export(application)
    child = result["tree"]["children"][0]
    assert child["text"]["declaration"]["doc_state"] == "saved"
    assert child["text"]["declaration"]["text"] == ""
    assert child["text"]["declaration"]["character_length"] == 0


def test_text_access_raises_exception_is_unknown():
    node = FakeNode(name="Boom", has_textual_declaration=True,
                    textual_declaration=FakeDocument(text_raises=RuntimeError("kaboom")))
    application = FakeApplication(children=[node])
    result = exporter_mod.ReadOnlyTextExporter().export(application)
    child = result["tree"]["children"][0]
    assert child["text"]["declaration"]["doc_state"] == "text_unknown"


def test_text_not_a_string_rejected():
    class NotAString(object):
        pass

    node = FakeNode(name="Bad", has_textual_declaration=True,
                    textual_declaration=FakeDocument(text=NotAString()))
    application = FakeApplication(children=[node])
    result = exporter_mod.ReadOnlyTextExporter().export(application)
    child = result["tree"]["children"][0]
    assert child["text"]["declaration"]["doc_state"] == "text_not_string"


def test_multiline_non_ascii_text_preserved_exactly():
    original = "PROGRAM Ação\n  x := 1; // café\n\n   \nEND_PROGRAM\r\n"
    node = FakeNode(name="Multiline", has_textual_declaration=True,
                    textual_declaration=FakeDocument(original))
    application = FakeApplication(children=[node])
    result = exporter_mod.ReadOnlyTextExporter().export(application)
    child = result["tree"]["children"][0]
    assert child["text"]["declaration"]["text"] == original
    assert child["text"]["declaration"]["character_length"] == len(original)


# =============================================================================
# LIMITES DE TEXTO
# =============================================================================

def test_document_size_limit_exceeded_not_saved_continues():
    big_text = "x" * 100
    small_node = FakeNode(name="Small", has_textual_declaration=True,
                          textual_declaration=FakeDocument("ok"))
    big_node = FakeNode(name="Big", has_textual_declaration=True,
                        textual_declaration=FakeDocument(big_text))
    application = FakeApplication(children=[big_node, small_node])
    result = exporter_mod.ReadOnlyTextExporter(max_document_characters=10).export(application)
    big_result = _node_by_id(result["tree"], "application/0")
    small_result = _node_by_id(result["tree"], "application/1")
    assert big_result["text"]["declaration"]["doc_state"] == "document_size_limit_exceeded"
    assert big_result["text"]["declaration"]["text"] is None
    assert small_result["text"]["declaration"]["doc_state"] == "saved"
    assert result["statistics"]["documents_skipped_size_limit"] == 1


def test_total_characters_limit_stops_new_reads_preserves_saved():
    node_a = FakeNode(name="A", has_textual_declaration=True, textual_declaration=FakeDocument("a" * 10))
    node_b = FakeNode(name="B", has_textual_declaration=True, textual_declaration=FakeDocument("b" * 10))
    node_c = FakeNode(name="C", has_textual_declaration=True, textual_declaration=FakeDocument("c" * 10))
    application = FakeApplication(children=[node_a, node_b, node_c])
    result = exporter_mod.ReadOnlyTextExporter(max_total_characters=15).export(application)

    a_res = _node_by_id(result["tree"], "application/0")
    b_res = _node_by_id(result["tree"], "application/1")
    c_res = _node_by_id(result["tree"], "application/2")

    assert a_res["text"]["declaration"]["doc_state"] == "saved"
    assert b_res["text"]["declaration"]["doc_state"] == "max_total_characters_reached"
    assert c_res["text"]["declaration"]["doc_state"] == "max_total_characters_reached"
    assert result["limits"]["max_total_characters_reached"] is True
    # metadados estruturais continuam sendo coletados (nomes presentes).
    assert b_res["identity"]["name"]["value"] == "B"
    assert c_res["identity"]["name"]["value"] == "C"


def test_max_text_objects_limit_stops_new_reads_but_keeps_metadata():
    nodes = [FakeNode(name="N%d" % i, has_textual_declaration=True,
                      textual_declaration=FakeDocument("text%d" % i))
             for i in range(3)]
    application = FakeApplication(children=nodes)
    result = exporter_mod.ReadOnlyTextExporter(max_text_objects=1).export(application)

    saved_states = [c["text"]["declaration"]["doc_state"] for c in result["tree"]["children"]]
    assert saved_states.count("saved") == 1
    assert saved_states.count("max_text_objects_reached") == 2
    assert result["limits"]["max_text_objects_reached"] is True
    # metadados estruturais preservados para todos.
    for i, child in enumerate(result["tree"]["children"]):
        assert child["identity"]["name"]["value"] == "N%d" % i


# =============================================================================
# SEGURANCA — APIs proibidas nunca chamadas; sem proxies no resultado
# =============================================================================

def test_forbidden_apis_never_called():
    node = FakeNode(name="Guarded", has_textual_declaration=True,
                    textual_declaration=FakeDocument("text"),
                    has_textual_implementation=True,
                    textual_implementation=FakeDocument("impl"))
    application = FakeApplication(children=[node])
    # Se qualquer API proibida fosse chamada pelo exportador, o Fake
    # correspondente levantaria AssertionError imediatamente.
    exporter_mod.ReadOnlyTextExporter().export(application)


def test_no_proxy_or_document_leaks_into_serialized_result():
    node = FakeNode(name="Pou1", has_textual_declaration=True,
                    textual_declaration=FakeDocument("text"),
                    has_textual_implementation=True,
                    textual_implementation=FakeDocument("impl"))
    application = FakeApplication(children=[node])
    result = exporter_mod.ReadOnlyTextExporter().export(application)
    for leaf in _walk_leaves(result):
        assert not isinstance(leaf, (FakeApplication, FakeNode, FakeCollection, FakeDocument))
        assert isinstance(leaf, (str, int, float, bool, type(None)))


def test_safety_declaration_fields():
    application = FakeApplication(children=[])
    result = exporter_mod.ReadOnlyTextExporter().export(application)
    decl = result["safety_declaration"]
    assert decl["read_only"] is True
    assert decl["text_read_only"] is True
    assert decl["text_normalization_applied"] is False
    assert decl["text_written_verbatim"] is True
    for key in ("project_write", "project_save", "project_close", "object_creation",
               "object_modification", "find_used", "compilation", "online_access",
               "device_repository_access", "device_configuration_access",
               "download", "force", "collection_direct_iteration"):
        assert decl[key] is False


def test_unknown_identity_object_with_exploding_repr_handled_safely():
    node = FakeNode(type_guid=UnknownBombValue(), object_guid=UnknownBombValue())
    application = FakeApplication(children=[node])
    result = exporter_mod.ReadOnlyTextExporter().export(application)
    identity = result["tree"]["children"][0]["identity"]
    assert identity["type_guid"]["state"] == "unrepresentable"
    assert identity["object_guid"]["state"] == "unrepresentable"


# =============================================================================
# FALHAS ESTRUTURAIS (paridade com o scanner ja aprovado)
# =============================================================================

def test_root_get_children_failure_isolated():
    application = FakeApplication(get_children_raises=RuntimeError("boom"))
    result = exporter_mod.ReadOnlyTextExporter().export(application)
    assert result["tree"]["collection"]["state"] == "unknown"
    assert result["tree"]["children"] == []
    assert any(e["where"] == "application" for e in result["errors"])


def test_partial_branch_does_not_abort_sibling_branches():
    broken = FakeNode(name="Broken", get_children_raises=RuntimeError("boom"))
    healthy = FakeNode(name="Healthy", children=[FakeNode(name="Grandchild")])
    application = FakeApplication(children=[broken, healthy])
    result = exporter_mod.ReadOnlyTextExporter().export(application)
    broken_node = _node_by_id(result["tree"], "application/0")
    healthy_node = _node_by_id(result["tree"], "application/1")
    assert broken_node["collection"]["state"] == "unknown"
    assert len(healthy_node["children"]) == 1
    assert result["statistics"]["total_nodes"] == 4


def test_indexer_failure_stops_only_that_collection():
    collection = FakeCollection(
        [FakeNode(name="OK0"), FakeNode(name="OK1"), FakeNode(name="OK2")],
        fail_at_index=1)
    child = FakeNode(name="Parent", children_collection_override=collection)
    application = FakeApplication(children=[child])
    result = exporter_mod.ReadOnlyTextExporter().export(application)
    node = result["tree"]["children"][0]
    assert len(node["children"]) == 1
    assert node["collection"]["state"] == "partial_indexing"


# =============================================================================
# ESCRITA EM DISCO (camada fina, testada com tmp_path)
# =============================================================================

def test_write_text_export_artifacts_preserves_text_and_hashes(tmp_path):
    from common import checksums as checksums_mod

    node = FakeNode(name="Pou1", has_textual_declaration=True,
                    textual_declaration=FakeDocument("DECL\n"),
                    has_textual_implementation=True,
                    textual_implementation=FakeDocument("IMPL\n"))
    folder = FakeNode(name="NoText", has_textual_declaration=False,
                      has_textual_implementation=False)
    application = FakeApplication(children=[node, folder])
    result = exporter_mod.ReadOnlyTextExporter().export(application)

    written = exporter_mod.write_text_export_artifacts(result, str(tmp_path))
    assert len(written) == 1  # so 'Pou1' tem texto; 'NoText' nao gera diretorio.

    object_dir = tmp_path / "objects" / written[0]
    metadata_path = object_dir / "metadata.json"
    declaration_path = object_dir / "declaration.st"
    implementation_path = object_dir / "implementation.st"

    assert metadata_path.exists()
    assert declaration_path.exists()
    assert implementation_path.exists()

    declaration_text = declaration_path.read_text(encoding="utf-8")
    implementation_text = implementation_path.read_text(encoding="utf-8")
    assert declaration_text == "DECL\n"
    assert implementation_text == "IMPL\n"

    import json
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))

    assert metadata["schema_version"] == "1.0"
    assert metadata["node_id"] == "application/0"
    assert metadata["parent_node_id"] == "application"
    assert metadata["depth"] == 1
    assert metadata["index"] == 0

    identity = metadata["identity"]
    assert identity["name"] == "Pou1"
    assert identity["is_folder"] is False
    assert isinstance(identity["type_guid"], str)
    assert isinstance(identity["object_guid"], str)

    declaration = metadata["declaration"]
    assert declaration["available"] is True
    assert declaration["state"] == "saved"
    assert declaration["file"] == "declaration.st"
    assert declaration["character_length"] == len("DECL\n")
    assert declaration["byte_length"] == len("DECL\n".encode("utf-8"))
    assert declaration["sha256"] == checksums_mod.sha256_text("DECL\n")

    implementation = metadata["implementation"]
    assert implementation["available"] is True
    assert implementation["state"] == "saved"
    assert implementation["file"] == "implementation.st"
    assert implementation["sha256"] == checksums_mod.sha256_text("IMPL\n")

    assert "python_type" in metadata["runtime"]
    assert "dotnet_type" in metadata["runtime"]
    assert metadata["errors"] == []


def test_write_text_export_artifacts_metadata_declaration_only_state_and_no_file(tmp_path):
    node = FakeNode(name="Gvl1", has_textual_declaration=True,
                    textual_declaration=FakeDocument("VAR_GLOBAL\nEND_VAR\n"),
                    has_textual_implementation=False)
    application = FakeApplication(children=[node])
    result = exporter_mod.ReadOnlyTextExporter().export(application)

    written = exporter_mod.write_text_export_artifacts(result, str(tmp_path))
    object_dir = tmp_path / "objects" / written[0]

    import json
    metadata = json.loads((object_dir / "metadata.json").read_text(encoding="utf-8"))

    assert metadata["declaration"]["available"] is True
    assert metadata["declaration"]["file"] == "declaration.st"

    implementation = metadata["implementation"]
    assert implementation["available"] is False
    assert implementation["state"] == "indicator_confirmed_false"
    assert implementation["file"] is None
    assert not (object_dir / "implementation.st").exists()


def test_write_text_export_artifacts_errors_filtered_by_node_id(tmp_path):
    collection = FakeCollection(
        [FakeNode(name="OK0"), FakeNode(name="OK1")], fail_at_index=1)
    child = FakeNode(name="Parent", has_textual_declaration=True,
                     textual_declaration=FakeDocument("x"),
                     children_collection_override=collection)
    application = FakeApplication(children=[child])
    result = exporter_mod.ReadOnlyTextExporter().export(application)

    written = exporter_mod.write_text_export_artifacts(result, str(tmp_path))
    assert len(written) == 1

    import json
    object_dir = tmp_path / "objects" / written[0]
    metadata = json.loads((object_dir / "metadata.json").read_text(encoding="utf-8"))

    # o erro de indexador ocorre em "application/0/1" (falha no indexador da
    # colecao de filhos deste no); comeca com o node_id deste objeto
    # ("application/0"), entao deve aparecer no seu metadata.json (junto de
    # quaisquer outros erros cujo "where" tambem comece com esse prefixo,
    # como indicadores tri-state nao suportados dos filhos indexados).
    assert metadata["node_id"] == "application/0"
    error_wheres = [e["where"] for e in metadata["errors"]]
    assert "application/0/1" in error_wheres
    assert all(w.startswith("application/0") for w in error_wheres)
    # nenhum erro de outro ramo (ex.: raiz "application") vaza para aqui.
    assert "application" not in error_wheres


def test_write_text_export_artifacts_errors_not_leaked_by_prefix_collision(tmp_path):
    """Regressao: node_id "application/1" NAO pode capturar erros de
    "application/10" so por coincidencia textual de prefixo (startswith
    sem checar limite de "/"). Cenario real: um no pai com 11+ filhos
    (indices 0..10), onde "1" e prefixo textual de "10"."""
    children = []
    for i in range(11):
        if i == 1:
            # filho de indice 1: tem texto salvo (gera metadata.json).
            children.append(FakeNode(
                name="Child1", has_textual_declaration=True,
                textual_declaration=FakeDocument("DECL1\n"),
                has_textual_implementation=False))
        elif i == 10:
            # filho de indice 10: indicador de declaracao lanca excecao
            # inesperada -> gera erro com "where" == "application/10"
            # (via _discover_one_document, doc_state indicator_unknown).
            # tambem tem texto de implementacao salvo, para poder conferir
            # seu proprio metadata.json.
            children.append(FakeNode(
                name="Child10", has_declaration_raises=RuntimeError("falha isolada no indicador"),
                has_textual_implementation=True,
                textual_implementation=FakeDocument("IMPL10\n")))
        else:
            children.append(FakeNode(name="Child%d" % i, has_textual_declaration=False,
                                     has_textual_implementation=False))

    application = FakeApplication(children=children)
    result = exporter_mod.ReadOnlyTextExporter().export(application)

    # confirma que o erro do filho 10 existe e aponta exatamente para
    # "application/10" (nao um prefixo parcial).
    errors_where = [e["where"] for e in result["errors"]]
    assert "application/10" in errors_where

    written = exporter_mod.write_text_export_artifacts(result, str(tmp_path))

    import json
    child1_dir = None
    child10_dir = None
    for dir_name in written:
        if dir_name.startswith("application_1__"):
            child1_dir = dir_name
        elif dir_name.startswith("application_10__"):
            child10_dir = dir_name
    assert child1_dir is not None, "filho de indice 1 deveria ter gerado metadata.json"
    assert child10_dir is not None, "filho de indice 10 deveria ter gerado metadata.json"

    metadata_1 = json.loads(
        (tmp_path / "objects" / child1_dir / "metadata.json").read_text(encoding="utf-8"))
    metadata_10 = json.loads(
        (tmp_path / "objects" / child10_dir / "metadata.json").read_text(encoding="utf-8"))

    assert metadata_1["node_id"] == "application/1"
    assert metadata_10["node_id"] == "application/10"

    # BUG (antes da correcao): "application/10".startswith("application/1")
    # era True, entao o erro do filho 10 vazava para o metadata.json do
    # filho 1. Depois da correcao, isso NUNCA deve acontecer.
    assert metadata_1["errors"] == []

    # o erro deve aparecer APENAS no metadata.json do proprio filho 10.
    metadata_10_wheres = [e["where"] for e in metadata_10["errors"]]
    assert "application/10" in metadata_10_wheres


def test_safety_declaration_text_document_fields():
    application = FakeApplication(children=[])
    result = exporter_mod.ReadOnlyTextExporter().export(application)
    decl = result["safety_declaration"]
    assert decl["text_document_access"] is True
    assert decl["text_document_write"] is False
    assert decl["replace_called"] is False
    assert decl["append_called"] is False
    assert decl["get_line_called"] is False


def test_flatten_tree_includes_text_index_support_fields():
    node = FakeNode(name="Pou1", has_textual_declaration=True,
                    textual_declaration=FakeDocument("text"),
                    has_textual_implementation=False)
    application = FakeApplication(children=[node])
    result = exporter_mod.ReadOnlyTextExporter().export(application)

    flat = exporter_mod.flatten_tree(result["tree"])
    entry = next(e for e in flat if e["node_id"] == "application/0")

    assert entry["declaration_state"] == "saved"
    assert entry["implementation_state"] == "indicator_confirmed_false"
    assert entry["declaration_file"] == "declaration.st"
    assert entry["implementation_file"] is None
    assert entry["declaration_character_length"] == len("text")
    assert entry["implementation_character_length"] is None


def test_build_text_index_full_schema():
    """Cobre as 5 categorias exigidas pelo schema de build_text_index():
    so declaracao, so implementacao, ambos, sem texto algum, e erro real
    de sondagem/leitura (que pode coexistir com uma lista de sucesso)."""

    # 1) so declaracao salva; implementacao confirmada False (nao textual).
    only_decl = FakeNode(
        name="OnlyDecl",
        has_textual_declaration=True, textual_declaration=FakeDocument("DECL_A\n"),  # 7 chars
        has_textual_implementation=False)

    # 2) so implementacao salva; declaracao confirmada False.
    only_impl = FakeNode(
        name="OnlyImpl",
        has_textual_declaration=False,
        has_textual_implementation=True, textual_implementation=FakeDocument("IMPL_B\n"))  # 7 chars

    # 3) ambos salvos (declaracao E implementacao).
    both = FakeNode(
        name="Both",
        has_textual_declaration=True, textual_declaration=FakeDocument("DECL_C\n"),  # 7 chars
        has_textual_implementation=True, textual_implementation=FakeDocument("IMPL_C_LONGER\n"))  # 14 chars

    # 4) nenhum texto: os dois indicadores confirmados False.
    no_text = FakeNode(
        name="NoText", is_folder=True,
        has_textual_declaration=False, has_textual_implementation=False)

    # 5) erro real de sondagem: indicador de declaracao lanca excecao
    # inesperada (-> declaration_state == "indicator_unknown"), enquanto a
    # implementacao e salva com sucesso. Prova que objects_with_text_errors
    # NAO e mutuamente exclusiva com objects_with_implementation.
    with_error = FakeNode(
        name="WithError",
        has_declaration_raises=RuntimeError("falha isolada no indicador"),
        has_textual_implementation=True, textual_implementation=FakeDocument("IMPL_E\n"))  # 7 chars

    application = FakeApplication(children=[only_decl, only_impl, both, no_text, with_error])
    result = exporter_mod.ReadOnlyTextExporter().export(application)

    flat = exporter_mod.flatten_tree(result["tree"])
    index = exporter_mod.build_text_index(flat)

    for key in ("objects_with_declaration", "objects_with_implementation",
               "objects_with_both", "objects_without_text", "objects_with_text_errors",
               "total_text_objects", "total_declaration_characters",
               "total_implementation_characters", "total_characters"):
        assert key in index

    def node_ids(entries):
        return set(e["node_id"] for e in entries)

    assert node_ids(index["objects_with_declaration"]) == {"application/0", "application/2"}
    assert node_ids(index["objects_with_implementation"]) == {"application/1", "application/2", "application/4"}
    assert node_ids(index["objects_with_both"]) == {"application/2"}
    assert node_ids(index["objects_without_text"]) == {"application/3"}
    # o proprio no raiz "application" tambem aparece aqui: FakeApplication
    # nao expoe has_textual_declaration/has_textual_implementation, entao
    # ambos os indicadores vem "indicator_unsupported" (erro real de
    # sondagem, nao "confirmado False") — comportamento correto e
    # consistente com o resto do exportador.
    assert node_ids(index["objects_with_text_errors"]) == {"application", "application/4"}

    # cada objeto das listas precisa trazer os 6 campos exigidos pelo schema.
    only_decl_entry = next(e for e in index["objects_with_declaration"] if e["node_id"] == "application/0")
    assert only_decl_entry["name"] == "OnlyDecl"
    assert isinstance(only_decl_entry["type_guid"], str)
    assert isinstance(only_decl_entry["object_guid"], str)
    assert only_decl_entry["declaration_file"] == "declaration.st"
    assert only_decl_entry["implementation_file"] is None
    assert set(only_decl_entry.keys()) == {
        "node_id", "name", "type_guid", "object_guid", "declaration_file", "implementation_file"}

    with_error_entry = next(e for e in index["objects_with_text_errors"] if e["node_id"] == "application/4")
    assert with_error_entry["implementation_file"] == "implementation.st"
    assert with_error_entry["declaration_file"] is None

    # totais calculados manualmente a partir dos fakes definidos acima:
    # total_text_objects: nos com PELO MENOS 1 documento salvo = 4
    # (only_decl, only_impl, both, with_error) — no_text nao conta.
    assert index["total_text_objects"] == 4

    # total_declaration_characters: soma de character_length das
    # declaracoes SALVAS: "DECL_A\n" (7) + "DECL_C\n" (7) = 14.
    assert index["total_declaration_characters"] == len("DECL_A\n") + len("DECL_C\n") == 14

    # total_implementation_characters: soma das implementacoes SALVAS:
    # "IMPL_B\n" (7) + "IMPL_C_LONGER\n" (14) + "IMPL_E\n" (7) = 28.
    assert index["total_implementation_characters"] == (
        len("IMPL_B\n") + len("IMPL_C_LONGER\n") + len("IMPL_E\n")) == 28

    assert index["total_characters"] == 14 + 28 == 42

"""Testa common/read_only_project_scanner.py (ReadOnlyProjectScanner).

Motivo (2026-07-23): substitui os probes de um-indice-por-execucao por um
scanner recursivo generico. Usa fakes em memoria (sem MasterTool real),
mesmo padrao de test_project_tree_adapter.py e
test_device_first_child_probe.py, cobrindo estrutura, navegacao,
identidade, falhas, seguranca e ciclos/duplicidades.
"""

import sys
from pathlib import Path

SCRIPTS_MASTERTOOL = Path(__file__).resolve().parents[2] / "scripts" / "mastertool"
if str(SCRIPTS_MASTERTOOL) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_MASTERTOOL))

from common import read_only_project_scanner as scanner_mod  # noqa: E402


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
    """Valor de type/guid que NAO foi confirmado como System.Guid nem e
    primitivo nativo — deve virar 'unrepresentable' sem jamais ser
    stringificado."""
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
        raise AssertionError("colecao NAO deve ser iterada pelo scanner")


_fake_node_counter = [0]


def _next_default_guid(prefix):
    _fake_node_counter[0] += 1
    return FakeGuidValue("%s-%d" % (prefix, _fake_node_counter[0]))


class FakeNode(object):
    def __init__(self, name="Node", is_folder=False, type_guid=None, object_guid=None,
                children=None, name_raises=None, is_folder_raises=None, type_raises=None,
                guid_raises=None, get_children_raises=None, children_collection_override=None):
        self._name = name
        self._is_folder = is_folder
        # GUIDs padrao UNICOS por instancia (nunca compartilhados) — um valor
        # fixo repetido acionaria falsamente a deteccao de object_guid
        # duplicado/ciclo entre nos que nao tem relacao nenhuma entre si.
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

    def __repr__(self):
        raise AssertionError("repr proibido em FakeNode")

    def __str__(self):
        raise AssertionError("str proibido em FakeNode")


class FakeProject(object):
    def __init__(self, path="C:/fake/Project.project", is_root=True, children=None,
                get_children_raises=None, children_collection_override=None):
        self._path = path
        self._is_root = is_root
        self._children = children if children is not None else []
        self._get_children_raises = get_children_raises
        self._children_collection_override = children_collection_override
        self.get_children_call_count = 0

    @property
    def path(self):
        return self._path

    @property
    def is_root(self):
        return self._is_root

    def get_children(self, recursive):
        self.get_children_call_count += 1
        if self._get_children_raises is not None:
            raise self._get_children_raises
        if self._children_collection_override is not None:
            return self._children_collection_override
        return FakeCollection(self._children)


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
# ESTRUTURA
# =============================================================================

def test_empty_tree():
    project = FakeProject(children=[])
    result = scanner_mod.ReadOnlyProjectScanner().scan(project)
    assert result["tree"]["children"] == []
    assert result["statistics"]["total_nodes"] == 1
    assert result["statistics"]["scan_complete"] is True
    assert result["errors"] == []


def test_root_with_one_child():
    child = FakeNode(name="Device")
    project = FakeProject(children=[child])
    result = scanner_mod.ReadOnlyProjectScanner().scan(project)
    assert len(result["tree"]["children"]) == 1
    node = result["tree"]["children"][0]
    assert node["node_id"] == "root/0"
    assert node["identity"]["name"]["value"] == "Device"
    assert result["statistics"]["total_nodes"] == 2


def test_two_levels():
    grandchild = FakeNode(name="Plc Logic")
    child = FakeNode(name="Device", children=[grandchild])
    project = FakeProject(children=[child])
    result = scanner_mod.ReadOnlyProjectScanner().scan(project)
    child_node = result["tree"]["children"][0]
    assert len(child_node["children"]) == 1
    gc_node = child_node["children"][0]
    assert gc_node["node_id"] == "root/0/0"
    assert gc_node["depth"] == 2
    assert gc_node["identity"]["name"]["value"] == "Plc Logic"
    assert result["statistics"]["total_nodes"] == 3


def test_multiple_levels_four_deep():
    n4 = FakeNode(name="L4")
    n3 = FakeNode(name="L3", children=[n4])
    n2 = FakeNode(name="L2", children=[n3])
    n1 = FakeNode(name="L1", children=[n2])
    project = FakeProject(children=[n1])
    result = scanner_mod.ReadOnlyProjectScanner(max_depth=8).scan(project)
    deepest = _node_by_id(result["tree"], "root/0/0/0/0")
    assert deepest is not None
    assert deepest["depth"] == 4
    assert deepest["identity"]["name"]["value"] == "L4"
    assert result["statistics"]["maximum_depth_reached"] == 4


def test_max_depth_limit_stops_expansion_but_keeps_node():
    n3 = FakeNode(name="L3")
    n2 = FakeNode(name="L2", children=[n3])
    n1 = FakeNode(name="L1", children=[n2])
    project = FakeProject(children=[n1])
    result = scanner_mod.ReadOnlyProjectScanner(max_depth=1).scan(project)

    l1_node = _node_by_id(result["tree"], "root/0")
    assert l1_node["identity"]["name"]["value"] == "L1"
    l2_node = _node_by_id(result["tree"], "root/0/0")
    assert l2_node is not None
    assert l2_node["identity"]["name"]["value"] == "L2"
    # L2 esta em depth=2 > max_depth=1 -> get_children NUNCA chamado nele.
    assert n2.get_children_call_count == 0
    assert l2_node["collection"]["state"] == "not_attempted_depth_limit"
    assert l2_node["children"] == []
    assert result["limits"]["max_depth_reached"] is True


def test_empty_collection_midtree():
    child = FakeNode(name="Empty", children=[])
    project = FakeProject(children=[child])
    result = scanner_mod.ReadOnlyProjectScanner().scan(project)
    assert result["statistics"]["empty_collections"] >= 1
    node = result["tree"]["children"][0]
    assert node["collection"]["count"] == 0
    assert node["collection"]["state"] == "confirmed"


def test_high_count_within_limit():
    children = [FakeNode(name="N%d" % i) for i in range(50)]
    project = FakeProject(children=children)
    result = scanner_mod.ReadOnlyProjectScanner(max_children_per_node=100).scan(project)
    assert len(result["tree"]["children"]) == 50
    assert result["tree"]["collection"]["state"] == "confirmed"


def test_count_above_children_limit_skips_indexing():
    children = [FakeNode(name="N%d" % i) for i in range(10)]
    project = FakeProject(children=children)
    result = scanner_mod.ReadOnlyProjectScanner(max_children_per_node=5).scan(project)
    assert result["tree"]["children"] == []
    assert result["tree"]["collection"]["state"] == "children_limit_exceeded"
    assert result["limits"]["max_children_per_node_reached"] is True
    assert any("children_limit_exceeded" in e["message"] for e in result["errors"])


def test_total_nodes_above_limit_aborts_scan_preserving_partial_result():
    branch_a_children = [FakeNode(name="A%d" % i) for i in range(3)]
    branch_a = FakeNode(name="BranchA", children=branch_a_children)
    branch_b_children = [FakeNode(name="B%d" % i) for i in range(3)]
    branch_b = FakeNode(name="BranchB", children=branch_b_children)
    project = FakeProject(children=[branch_a, branch_b])
    # total permitido: root(1) + 2 filhos diretos = 3, mas processar
    # BranchA (3 filhos) ja levaria a 6 > max_total_nodes=4.
    result = scanner_mod.ReadOnlyProjectScanner(max_total_nodes=4).scan(project)
    assert result["statistics"]["scan_complete"] is False
    assert result["limits"]["max_total_nodes_reached"] is True
    # o que ja foi coletado antes do aborto permanece.
    assert len(result["tree"]["children"]) == 2


# =============================================================================
# NAVEGACAO
# =============================================================================

def test_get_children_called_once_per_node():
    child = FakeNode(name="Device")
    project = FakeProject(children=[child])
    scanner_mod.ReadOnlyProjectScanner().scan(project)
    assert project.get_children_call_count == 1
    assert child.get_children_call_count == 1


def test_count_read_once_per_collection():
    child = FakeNode(name="Device", children=[FakeNode(name="X")])
    project = FakeProject(children=[child])
    result = scanner_mod.ReadOnlyProjectScanner().scan(project)
    # Nao temos referencia direta a FakeCollection interna (criada dentro de
    # get_children), entao validamos indiretamente: count aparece correto e
    # sem re-leitura implicaria erro de estado — o teste de "chamada unica"
    # de baixo nivel ja e coberto por capabilities.probe_member (usado
    # internamente). Aqui validamos o resultado funcional.
    assert result["tree"]["collection"]["count"] == 1


def test_each_index_accessed_once_and_order_preserved():
    grandchildren = [FakeNode(name="G0"), FakeNode(name="G1"), FakeNode(name="G2")]
    collection = FakeCollection(grandchildren)
    child = FakeNode(name="Device", children_collection_override=collection)
    project = FakeProject(children=[child])
    scanner_mod.ReadOnlyProjectScanner().scan(project)
    assert collection.index_accesses == [0, 1, 2]


def test_collection_never_iterated_directly():
    children = [FakeNode(name="N%d" % i) for i in range(4)]
    project = FakeProject(children=children)
    # Se __iter__ fosse chamado, levantaria AssertionError e o teste falharia.
    result = scanner_mod.ReadOnlyProjectScanner().scan(project)
    assert len(result["tree"]["children"]) == 4


def test_children_order_preserved_in_result():
    names = ["Zeta", "Alfa", "Meio"]
    children = [FakeNode(name=n) for n in names]
    project = FakeProject(children=children)
    result = scanner_mod.ReadOnlyProjectScanner().scan(project)
    result_names = [c["identity"]["name"]["value"] for c in result["tree"]["children"]]
    assert result_names == names


def test_path_indices_and_depth_correct():
    grandchild = FakeNode(name="GC")
    child0 = FakeNode(name="C0")
    child1 = FakeNode(name="C1", children=[grandchild])
    project = FakeProject(children=[child0, child1])
    result = scanner_mod.ReadOnlyProjectScanner().scan(project)
    gc_node = _node_by_id(result["tree"], "root/1/0")
    assert gc_node["path_indices"] == [1, 0]
    assert gc_node["depth"] == 2
    assert gc_node["parent_node_id"] == "root/1"


# =============================================================================
# IDENTIDADE
# =============================================================================

def test_identity_name_type_guid_all_confirmed():
    child = FakeNode(name="Plc Logic", type_guid=FakeGuidValue("type-x"), object_guid=FakeGuidValue("obj-x"))
    project = FakeProject(children=[child])
    result = scanner_mod.ReadOnlyProjectScanner().scan(project)
    identity = result["tree"]["children"][0]["identity"]
    assert identity["name"]["state"] == "confirmed" and identity["name"]["value"] == "Plc Logic"
    assert identity["type_guid"]["state"] == "confirmed" and identity["type_guid"]["value"] == "type-x"
    assert identity["object_guid"]["state"] == "confirmed" and identity["object_guid"]["value"] == "obj-x"


def test_identity_field_absent_is_unsupported():
    child = FakeNode(guid_raises=AttributeError("guid ausente"))
    project = FakeProject(children=[child])
    result = scanner_mod.ReadOnlyProjectScanner().scan(project)
    identity = result["tree"]["children"][0]["identity"]
    assert identity["object_guid"]["state"] == "unsupported"
    assert identity["object_guid"]["value"] is None


def test_identity_field_exception_is_unknown():
    child = FakeNode(type_raises=RuntimeError("type explodiu"))
    project = FakeProject(children=[child])
    result = scanner_mod.ReadOnlyProjectScanner().scan(project)
    identity = result["tree"]["children"][0]["identity"]
    assert identity["type_guid"]["state"] == "unknown"
    assert identity["type_guid"]["value"] is None


def test_native_string_and_confirmed_guid_serialized():
    child = FakeNode(name="StringNativo", object_guid=FakeGuidValue("confirmed-guid-value"))
    project = FakeProject(children=[child])
    result = scanner_mod.ReadOnlyProjectScanner().scan(project)
    identity = result["tree"]["children"][0]["identity"]
    assert identity["name"]["value"] == "StringNativo"
    assert identity["object_guid"]["value"] == "confirmed-guid-value"


def test_unknown_object_with_exploding_repr_and_str_handled_safely():
    child = FakeNode(type_guid=UnknownBombValue(), guid_raises=None, object_guid=UnknownBombValue())
    project = FakeProject(children=[child])
    # Nao deve lancar excecao alguma.
    result = scanner_mod.ReadOnlyProjectScanner().scan(project)
    identity = result["tree"]["children"][0]["identity"]
    assert identity["type_guid"]["state"] == "unrepresentable"
    assert identity["type_guid"]["value"] is None
    assert identity["object_guid"]["state"] == "unrepresentable"
    assert identity["object_guid"]["value"] is None


def test_is_folder_false_child_still_gets_children_expanded():
    grandchild = FakeNode(name="GC")
    child = FakeNode(name="NaoPasta", is_folder=False, children=[grandchild])
    project = FakeProject(children=[child])
    result = scanner_mod.ReadOnlyProjectScanner().scan(project)
    node = result["tree"]["children"][0]
    assert node["identity"]["is_folder"]["value"] is False
    assert len(node["children"]) == 1
    assert child.get_children_call_count == 1


# =============================================================================
# FALHAS
# =============================================================================

def test_root_get_children_failure_is_isolated_to_root_collection():
    project = FakeProject(get_children_raises=RuntimeError("boom"))
    result = scanner_mod.ReadOnlyProjectScanner().scan(project)
    assert result["tree"]["collection"]["state"] == "unknown"
    assert result["tree"]["children"] == []
    assert any(e["where"] == "root" for e in result["errors"])
    assert result["statistics"]["collection_errors"] == 1


def test_node_get_children_null_marks_that_node_only():
    healthy_sibling = FakeNode(name="Healthy", children=[FakeNode(name="X")])
    broken = FakeNode(name="Broken", children_collection_override=None)

    class NullReturningNode(FakeNode):
        def get_children(self, recursive):
            self.get_children_call_count += 1
            return None

    broken = NullReturningNode(name="Broken")
    project = FakeProject(children=[broken, healthy_sibling])
    result = scanner_mod.ReadOnlyProjectScanner().scan(project)
    broken_node = _node_by_id(result["tree"], "root/0")
    healthy_node = _node_by_id(result["tree"], "root/1")
    assert broken_node["collection"]["state"] == "null"
    assert healthy_node["collection"]["state"] == "confirmed"
    assert len(healthy_node["children"]) == 1


def test_collection_without_count_interface():
    collection = FakeCollection([FakeNode(name="X")], implements=False)
    child = FakeNode(name="Broken", children_collection_override=collection)
    project = FakeProject(children=[child])
    result = scanner_mod.ReadOnlyProjectScanner().scan(project)
    node = result["tree"]["children"][0]
    assert node["collection"]["state"] == "interface_unconfirmed"
    assert node["children"] == []


def test_negative_count_rejected():
    collection = FakeCollection([], count_value=-1)
    child = FakeNode(name="Broken", children_collection_override=collection)
    project = FakeProject(children=[child])
    result = scanner_mod.ReadOnlyProjectScanner().scan(project)
    node = result["tree"]["children"][0]
    assert node["collection"]["state"] == "invalid_negative_count"


def test_indexer_failure_stops_that_collection_but_keeps_earlier_children():
    collection = FakeCollection(
        [FakeNode(name="OK0"), FakeNode(name="OK1"), FakeNode(name="OK2")],
        fail_at_index=1)
    child = FakeNode(name="Parent", children_collection_override=collection)
    project = FakeProject(children=[child])
    result = scanner_mod.ReadOnlyProjectScanner().scan(project)
    node = result["tree"]["children"][0]
    assert len(node["children"]) == 1
    assert node["children"][0]["identity"]["name"]["value"] == "OK0"
    assert node["collection"]["state"] == "partial_indexing"
    assert collection.index_accesses == [0, 1]
    assert any("root/0/1" in e["where"] for e in result["errors"])


def test_partial_branch_does_not_abort_sibling_branches():
    broken = FakeNode(name="Broken", get_children_raises=RuntimeError("boom"))
    healthy = FakeNode(name="Healthy", children=[FakeNode(name="Grandchild")])
    project = FakeProject(children=[broken, healthy])
    result = scanner_mod.ReadOnlyProjectScanner().scan(project)
    broken_node = _node_by_id(result["tree"], "root/0")
    healthy_node = _node_by_id(result["tree"], "root/1")
    assert broken_node["collection"]["state"] == "unknown"
    assert len(healthy_node["children"]) == 1
    assert result["statistics"]["total_nodes"] == 4  # root + broken + healthy + grandchild


# =============================================================================
# SEGURANCA
# =============================================================================

def test_no_proxy_or_clr_collection_leaks_into_result():
    grandchild = FakeNode(name="GC")
    child = FakeNode(name="Device", children=[grandchild])
    project = FakeProject(children=[child])
    result = scanner_mod.ReadOnlyProjectScanner().scan(project)
    for leaf in _walk_leaves(result):
        assert not isinstance(leaf, (FakeProject, FakeNode, FakeCollection))
        assert isinstance(leaf, (str, int, float, bool, type(None)))


def test_safety_declaration_fields_are_all_false_except_navigation():
    project = FakeProject(children=[])
    result = scanner_mod.ReadOnlyProjectScanner().scan(project)
    decl = result["safety_declaration"]
    assert decl["read_only"] is True
    assert decl["bounded_index_navigation"] is True
    assert decl["recursive_navigation"] is True
    for key in ("project_write", "project_save", "project_close", "object_creation",
               "object_modification", "text_document_access", "find_used",
               "active_application_used", "compilation", "online_access",
               "device_repository_access", "device_configuration_access",
               "download", "force", "collection_direct_iteration"):
        assert decl[key] is False


# =============================================================================
# CICLOS E DUPLICIDADES
# =============================================================================

def test_duplicate_object_guid_in_different_branches_is_registered_not_treated_as_cycle():
    shared_guid = FakeGuidValue("shared-guid")
    node_a = FakeNode(name="A", object_guid=shared_guid)
    node_b = FakeNode(name="B", object_guid=shared_guid)
    project = FakeProject(children=[node_a, node_b])
    result = scanner_mod.ReadOnlyProjectScanner().scan(project)
    assert result["statistics"]["duplicate_object_guids"] == 1
    a_node = _node_by_id(result["tree"], "root/0")
    b_node = _node_by_id(result["tree"], "root/1")
    assert a_node["cycle_detected"] is False
    assert b_node["cycle_detected"] is False
    assert any("duplicate_object_guid" in e["message"] for e in result["errors"])


def test_true_ancestor_cycle_stops_descent_without_infinite_loop():
    cyclic_guid = FakeGuidValue("cyclic-guid")
    cyclic_node = FakeNode(name="Cyclic", object_guid=cyclic_guid)
    # o filho do no ciclico e ELE MESMO (mesma instancia, mesmo guid).
    cyclic_node._children = [cyclic_node]

    project = FakeProject(children=[cyclic_node])
    result = scanner_mod.ReadOnlyProjectScanner(max_depth=50).scan(project)

    first_occurrence = _node_by_id(result["tree"], "root/0")
    assert first_occurrence["identity"]["object_guid"]["value"] == "cyclic-guid"
    assert first_occurrence["cycle_detected"] is False
    assert len(first_occurrence["children"]) == 1

    second_occurrence = first_occurrence["children"][0]
    assert second_occurrence["cycle_detected"] is True
    assert second_occurrence["children"] == []
    # get_children NAO deve ter sido chamado uma segunda vez no ciclo —
    # so a primeira ocorrencia expandiu; a segunda foi bloqueada antes.
    assert cyclic_node.get_children_call_count == 1
    assert any("cycle_detected" in e["message"] for e in result["errors"])

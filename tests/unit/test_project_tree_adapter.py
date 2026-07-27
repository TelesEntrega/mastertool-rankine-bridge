"""Testa ProjectTreeAdapter (scripts/mastertool/common/project_tree_adapter.py).

Motivo (2026-07-23): apos os probes 05/06/07 confirmarem em runtime toda a
cadeia minima de navegacao contra ExemploPlanta V1.0.project, o
ProjectTreeAdapter foi aprovado como a alternativa LIMITADA e auditada ao
tree_walker.py (que segue suspenso). Estes testes usam fakes em memoria
(sem MasterTool real) para garantir, por construcao: profundidade <= 1,
uma unica chamada por membro sondado, nenhuma iteracao da colecao, nenhum
proxy vazando no resultado, e degradacao graciosa por-campo sem abortar o
snapshot inteiro (exceto para falhas estruturais em get_children/Count/
indexador, que devem abortar).
"""

import sys
from pathlib import Path

import pytest

SCRIPTS_MASTERTOOL = Path(__file__).resolve().parents[2] / "scripts" / "mastertool"
if str(SCRIPTS_MASTERTOOL) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_MASTERTOOL))

from common import project_tree_adapter as pta  # noqa: E402


class BombValue(object):
    """Objeto CLR desconhecido simulado: __repr__/__str__ levantam se
    chamados. Usado para provar que o adaptador nunca tenta stringificar um
    valor cujo tipo nao foi confirmado como seguro."""

    def __repr__(self):
        raise AssertionError("repr() chamado em objeto CLR desconhecido — violacao de politica")

    def __str__(self):
        raise AssertionError("str() chamado em objeto CLR desconhecido — violacao de politica")


class FakeNode(object):
    def __init__(self, name="Node", is_folder=False, type_guid="type-guid-0",
                object_guid="object-guid-0", name_raises=None, is_folder_raises=None,
                type_raises=None, guid_raises=None, is_folder_value=None,
                type_value=None, guid_value=None):
        self._name = name
        self._is_folder = is_folder if is_folder_value is None else is_folder_value
        self._type_guid = type_guid if type_value is None else type_value
        self._object_guid = object_guid if guid_value is None else guid_value
        self._name_raises = name_raises
        self._is_folder_raises = is_folder_raises
        self._type_raises = type_raises
        self._guid_raises = guid_raises
        self.name_call_count = 0
        self.property_access_count = {"is_folder": 0, "type": 0, "guid": 0}

    def get_name(self, recursive):
        self.name_call_count += 1
        if self._name_raises is not None:
            raise self._name_raises
        return self._name

    @property
    def is_folder(self):
        self.property_access_count["is_folder"] += 1
        if self._is_folder_raises is not None:
            raise self._is_folder_raises
        return self._is_folder

    @property
    def type(self):
        self.property_access_count["type"] += 1
        if self._type_raises is not None:
            raise self._type_raises
        return self._type_guid

    @property
    def guid(self):
        self.property_access_count["guid"] += 1
        if self._guid_raises is not None:
            raise self._guid_raises
        return self._object_guid


class FakeChildrenCollection(object):
    def __init__(self, items, count_value=None, count_raises=None,
                fail_at_index=None, fail_exception=None):
        self._items = list(items)
        self._count_value = count_value if count_value is not None else len(self._items)
        self._count_raises = count_raises
        self._fail_at_index = fail_at_index
        self._fail_exception = fail_exception or RuntimeError("falha simulada no indexador")
        self.count_access_count = 0
        self.index_accesses = []

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

    def __iter__(self):
        raise AssertionError("colecao CLR NAO deve ser iterada pelo adaptador")

    def GetEnumerator(self):
        raise AssertionError("GetEnumerator NAO deve ser chamado pelo adaptador")


class FakeProject(object):
    def __init__(self, path="C:/fake/ExemploPlanta.project", is_root=True,
                children_collection=None, get_children_raises=None):
        self._path = path
        self._is_root = is_root
        self._children_collection = children_collection
        self._get_children_raises = get_children_raises
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
        return self._children_collection


def _confirmed(field):
    return field["state"] == "confirmed"


# --- 1. colecao vazia --------------------------------------------------------
def test_empty_collection():
    project = FakeProject(children_collection=FakeChildrenCollection([]))
    snapshot = pta.ProjectTreeAdapter(project).get_root_children()
    assert snapshot["collection"]["state"] == "confirmed"
    assert snapshot["collection"]["count"] == 0
    assert snapshot["children"] == []
    assert snapshot["complete"] is True
    assert snapshot["errors"] == []


# --- 2. um elemento -----------------------------------------------------------
def test_single_element():
    node = FakeNode(name="Project Settings", type_guid="t-0", object_guid="g-0")
    project = FakeProject(children_collection=FakeChildrenCollection([node]))
    snapshot = pta.ProjectTreeAdapter(project).get_root_children()
    assert snapshot["collection"]["count"] == 1
    assert len(snapshot["children"]) == 1
    child = snapshot["children"][0]
    assert child["index"] == 0
    assert _confirmed(child["name"]) and child["name"]["value"] == "Project Settings"
    assert _confirmed(child["is_folder"]) and child["is_folder"]["value"] is False
    assert _confirmed(child["type_guid"]) and child["type_guid"]["value"] == "t-0"
    assert _confirmed(child["object_guid"]) and child["object_guid"]["value"] == "g-0"


# --- 3. quatro elementos ------------------------------------------------------
def test_four_elements():
    names = ["Project Settings", "Device", "Project Information", "__VisualizationStyle"]
    nodes = [FakeNode(name=n, type_guid="t-%s" % i, object_guid="g-%s" % i)
            for i, n in enumerate(names)]
    project = FakeProject(children_collection=FakeChildrenCollection(nodes))
    snapshot = pta.ProjectTreeAdapter(project).get_root_children()
    assert snapshot["collection"]["count"] == 4
    assert [c["name"]["value"] for c in snapshot["children"]] == names
    assert snapshot["complete"] is True


# --- 4. Count diferente do esperado -------------------------------------------
def test_count_differs_from_expected_does_not_abort():
    nodes = [FakeNode(name="A"), FakeNode(name="B"), FakeNode(name="C"), FakeNode(name="D")]
    project = FakeProject(children_collection=FakeChildrenCollection(nodes))
    snapshot = pta.ProjectTreeAdapter(project, expected_count=5).get_root_children()
    assert snapshot["collection"]["count"] == 4
    assert snapshot["collection"]["count_matches_expected"] is False
    # Nao aborta: Count pertence ao projeto, nao a API — enumeracao completa.
    assert len(snapshot["children"]) == 4
    assert snapshot["complete"] is True
    assert any(e["where"] == "children.Count" for e in snapshot["errors"])


def test_count_matches_expected_true():
    nodes = [FakeNode(name="A")]
    project = FakeProject(children_collection=FakeChildrenCollection(nodes))
    snapshot = pta.ProjectTreeAdapter(project, expected_count=1).get_root_children()
    assert snapshot["collection"]["count_matches_expected"] is True
    assert snapshot["errors"] == []


# --- 5. Count maior que max_children ------------------------------------------
def test_count_exceeds_max_children_aborts():
    collection = FakeChildrenCollection([], count_value=5)
    project = FakeProject(children_collection=collection)
    snapshot = pta.ProjectTreeAdapter(project, max_children=2).get_root_children()
    assert snapshot["collection"]["state"] == "invalid_count"
    assert snapshot["children"] == []
    assert snapshot["complete"] is False
    assert collection.index_accesses == []


# --- 6. Count negativo ---------------------------------------------------------
def test_negative_count_aborts():
    collection = FakeChildrenCollection([], count_value=-1)
    project = FakeProject(children_collection=collection)
    snapshot = pta.ProjectTreeAdapter(project).get_root_children()
    assert snapshot["collection"]["state"] == "invalid_count"
    assert snapshot["children"] == []
    assert snapshot["complete"] is False
    assert collection.index_accesses == []


# --- 7. falha em get_children(False) --------------------------------------------
def test_get_children_failure_aborts():
    project = FakeProject(get_children_raises=RuntimeError("get_children explodiu"))
    snapshot = pta.ProjectTreeAdapter(project).get_root_children()
    assert snapshot["collection"]["state"] == "unknown"
    assert snapshot["children"] == []
    assert snapshot["complete"] is False
    assert any(e["where"] == "get_children" for e in snapshot["errors"])
    assert project.get_children_call_count == 1


def test_get_children_unsupported_classified_correctly():
    project = FakeProject(get_children_raises=AttributeError("sem get_children"))
    snapshot = pta.ProjectTreeAdapter(project).get_root_children()
    assert snapshot["collection"]["state"] == "unsupported"


# --- 8. falha ao ler Count -------------------------------------------------------
def test_count_read_failure_aborts():
    collection = FakeChildrenCollection([], count_raises=RuntimeError("Count explodiu"))
    project = FakeProject(children_collection=collection)
    snapshot = pta.ProjectTreeAdapter(project).get_root_children()
    assert snapshot["collection"]["state"] == "unknown"
    assert snapshot["children"] == []
    assert snapshot["complete"] is False
    assert any(e["where"] == "children.Count" for e in snapshot["errors"])
    assert collection.count_access_count == 1


# --- 9. falha no indexador ---------------------------------------------------------
def test_indexer_failure_stops_enumeration_but_keeps_prior_nodes():
    nodes = [FakeNode(name="A"), FakeNode(name="B"), FakeNode(name="C")]
    collection = FakeChildrenCollection(nodes, fail_at_index=1)
    project = FakeProject(children_collection=collection)
    snapshot = pta.ProjectTreeAdapter(project).get_root_children()
    assert snapshot["collection"]["count"] == 3
    # indice 0 foi lido com sucesso ANTES da falha em 1 -> permanece.
    assert len(snapshot["children"]) == 1
    assert snapshot["children"][0]["name"]["value"] == "A"
    assert snapshot["complete"] is False
    assert any(e["where"] == "children[1]" for e in snapshot["errors"])
    # indice 2 NUNCA foi tentado: o loop para no primeiro erro de indexador.
    assert collection.index_accesses == [0, 1]


# --- 10. falha isolada em get_name(False) -------------------------------------------
def test_isolated_name_failure_does_not_abort_other_fields_or_nodes():
    broken = FakeNode(name_raises=RuntimeError("get_name explodiu"))
    healthy = FakeNode(name="Depois")
    project = FakeProject(children_collection=FakeChildrenCollection([broken, healthy]))
    snapshot = pta.ProjectTreeAdapter(project).get_root_children()
    assert snapshot["complete"] is True
    assert len(snapshot["children"]) == 2
    first = snapshot["children"][0]
    assert first["name"]["state"] == "unknown"
    assert first["name"]["value"] is None
    # is_folder/type/guid do MESMO no continuam sendo sondados normalmente.
    assert _confirmed(first["is_folder"])
    assert _confirmed(first["type_guid"])
    assert _confirmed(first["object_guid"])
    # o proximo no continua sendo processado normalmente.
    assert snapshot["children"][1]["name"]["value"] == "Depois"


# --- 11. falha isolada em type -------------------------------------------------------
def test_isolated_type_failure_does_not_abort():
    broken = FakeNode(type_raises=RuntimeError("type explodiu"))
    project = FakeProject(children_collection=FakeChildrenCollection([broken]))
    snapshot = pta.ProjectTreeAdapter(project).get_root_children()
    assert snapshot["complete"] is True
    child = snapshot["children"][0]
    assert child["type_guid"]["state"] == "unknown"
    assert child["type_guid"]["value"] is None
    assert _confirmed(child["name"])
    assert _confirmed(child["is_folder"])
    assert _confirmed(child["object_guid"])


# --- 12. ausencia de guid -------------------------------------------------------------
def test_missing_guid_classified_as_unsupported():
    node = FakeNode(guid_raises=AttributeError("guid nao existe neste objeto"))
    project = FakeProject(children_collection=FakeChildrenCollection([node]))
    snapshot = pta.ProjectTreeAdapter(project).get_root_children()
    child = snapshot["children"][0]
    assert child["object_guid"]["state"] == "unsupported"
    assert child["object_guid"]["value"] is None
    assert snapshot["complete"] is True


# --- 13. garantia de chamada unica por membro -----------------------------------------
def test_each_member_called_exactly_once_per_node_and_collection():
    nodes = [FakeNode(name="A"), FakeNode(name="B"), FakeNode(name="C")]
    collection = FakeChildrenCollection(nodes)
    project = FakeProject(children_collection=collection)
    pta.ProjectTreeAdapter(project).get_root_children()

    assert project.get_children_call_count == 1
    assert collection.count_access_count == 1
    assert collection.index_accesses == [0, 1, 2]
    for node in nodes:
        assert node.name_call_count == 1
        assert node.property_access_count == {"is_folder": 1, "type": 1, "guid": 1}


# --- 14. garantia de que a colecao nao foi iterada ------------------------------------
def test_collection_never_iterated():
    nodes = [FakeNode(name="A"), FakeNode(name="B")]
    collection = FakeChildrenCollection(nodes)
    project = FakeProject(children_collection=collection)
    # Se __iter__/GetEnumerator fossem chamados, levantariam AssertionError
    # e este teste falharia. Completar sem excecao PROVA que nao foram.
    snapshot = pta.ProjectTreeAdapter(project).get_root_children()
    assert snapshot["complete"] is True


# --- 15. garantia de que nenhum objeto proxy aparece no resultado ---------------------
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


def test_no_proxy_object_leaks_into_result():
    nodes = [FakeNode(name="A"), FakeNode(name="B")]
    collection = FakeChildrenCollection(nodes)
    project = FakeProject(children_collection=collection)
    snapshot = pta.ProjectTreeAdapter(project).get_root_children()
    for leaf in _walk_leaves(snapshot):
        assert not isinstance(leaf, (FakeProject, FakeChildrenCollection, FakeNode))
        assert isinstance(leaf, (str, int, float, bool, type(None)))


# --- 16. objeto com __repr__/__str__ explosivos ---------------------------------------
def test_node_with_exploding_repr_and_str_is_handled_safely():
    node = FakeNode(type_value=BombValue(), guid_value=BombValue())
    project = FakeProject(children_collection=FakeChildrenCollection([node]))
    # Nao deve levantar excecao alguma (BombValue.__repr__/__str__ levantariam
    # AssertionError se chamados).
    snapshot = pta.ProjectTreeAdapter(project).get_root_children()
    child = snapshot["children"][0]
    assert child["type_guid"]["state"] == "unrepresentable"
    assert child["type_guid"]["value"] is None
    assert child["object_guid"]["state"] == "unrepresentable"
    assert snapshot["complete"] is True


# --- 17. recusa de profundidade maior que 1 -------------------------------------------
def test_depth_greater_than_one_is_refused_without_touching_project():
    project = FakeProject(children_collection=FakeChildrenCollection([]))
    adapter = pta.ProjectTreeAdapter(project)
    with pytest.raises(pta.DepthNotSupportedError):
        adapter.get_root_children(depth=2)
    assert project.get_children_call_count == 0


def test_depth_zero_returns_root_only_without_calling_get_children():
    project = FakeProject(children_collection=FakeChildrenCollection([FakeNode(name="A")]))
    snapshot = pta.ProjectTreeAdapter(project).get_root_children(depth=0)
    assert snapshot["depth"] == 0
    assert snapshot["children"] == []
    assert project.get_children_call_count == 0
    assert snapshot["root"]["path"]["value"] == "C:/fake/ExemploPlanta.project"
    assert snapshot["root"]["is_root"]["value"] is True


def test_render_simplified_snapshot_flattens_field_states():
    node = FakeNode(name="Device", type_guid="t-1", object_guid="g-1")
    project = FakeProject(children_collection=FakeChildrenCollection([node]))
    snapshot = pta.ProjectTreeAdapter(project, expected_count=1).get_root_children()
    simplified = pta.render_simplified_snapshot(snapshot)
    assert simplified["root"]["path"] == "C:/fake/ExemploPlanta.project"
    assert simplified["root"]["is_root"] is True
    assert simplified["children"] == [{
        "index": 0, "name": "Device", "is_folder": False,
        "type_guid": "t-1", "object_guid": "g-1",
    }]

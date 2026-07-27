"""Testa common/graphic_language_inventory.py (GraphicLanguageInventory).

Motivo (2026-07-24): Fase L0 do roadmap Ladder (docs/14-ladder-roadmap.md).
Reaproveita a MESMA filosofia de fakes de test_read_only_text_exporter.py
(navegacao get_children/Count/indexador/identidade + indicadores tri-state
has_textual_declaration/has_textual_implementation), mas SEM nenhum
FakeDocument/`.text` (este modulo nunca le conteudo textual) e adicionando
cobertura da logica de CLASSIFICACAO em 4 estados (supported/
partially_supported/unsupported/unknown).
"""

import sys
from pathlib import Path

SCRIPTS_MASTERTOOL = Path(__file__).resolve().parents[2] / "scripts" / "mastertool"
if str(SCRIPTS_MASTERTOOL) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_MASTERTOOL))

from common import graphic_language_inventory as inv_mod  # noqa: E402


# =============================================================================
# FAKES (mesmo padrao de test_read_only_text_exporter.py)
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
        raise AssertionError("colecao NAO deve ser iterada pelo inventario")


class _ForbiddenApiMixin(object):
    """Mixin que faz QUALQUER chamada as APIs proibidas levantar
    AssertionError IMEDIATO — prova de que o inventario nunca as invoca."""

    def replace(self, *a, **k):
        raise AssertionError("replace() chamado — proibido")

    def append(self, *a, **k):
        raise AssertionError("append() chamado — proibido")

    def get_line(self, *a, **k):
        raise AssertionError("get_line() chamado — proibido")

    def create_pou(self, *a, **k):
        raise AssertionError("create_pou() chamado — proibido")

    def find(self, *a, **k):
        raise AssertionError("find() chamado — proibido")

    def build(self, *a, **k):
        raise AssertionError("build() chamado — proibido")

    def save(self, *a, **k):
        raise AssertionError("save() chamado — proibido")

    def close(self, *a, **k):
        raise AssertionError("close() chamado — proibido")


_fake_node_counter = [0]


def _next_default_guid(prefix):
    _fake_node_counter[0] += 1
    return FakeGuidValue("%s-%d" % (prefix, _fake_node_counter[0]))


class _TextAccessBomb(object):
    """Se algo tentar ler .text neste objeto, explode — prova de que o
    inventario NUNCA acessa o documento/.text, so os indicadores booleanos."""

    @property
    def text(self):
        raise AssertionError(".text acessado — proibido neste modulo (so inventario)")

    def __repr__(self):
        raise AssertionError("repr proibido em _TextAccessBomb")


class FakeNode(_ForbiddenApiMixin, object):
    def __init__(self, name="Node", is_folder=False, type_guid=None, object_guid=None,
                children=None, name_raises=None, is_folder_raises=None, type_raises=None,
                guid_raises=None, get_children_raises=None, children_collection_override=None,
                has_textual_declaration=None, has_declaration_raises=None,
                has_textual_implementation=None, has_implementation_raises=None):
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

        self._has_textual_declaration = has_textual_declaration
        self._has_declaration_raises = has_declaration_raises
        self._has_textual_implementation = has_textual_implementation
        self._has_implementation_raises = has_implementation_raises

        self.has_declaration_access_count = 0
        self.has_implementation_access_count = 0

        # Se algum codigo tentar ler o documento (nunca deveria: este modulo
        # e so indicadores), a bomba explode.
        self.textual_declaration = _TextAccessBomb()
        self.textual_implementation = _TextAccessBomb()

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

    @property
    def has_textual_declaration(self):
        self.has_declaration_access_count += 1
        if self._has_declaration_raises is not None:
            raise self._has_declaration_raises
        if self._has_textual_declaration is None:
            raise AttributeError("has_textual_declaration ausente")
        return self._has_textual_declaration

    @property
    def has_textual_implementation(self):
        self.has_implementation_access_count += 1
        if self._has_implementation_raises is not None:
            raise self._has_implementation_raises
        if self._has_textual_implementation is None:
            raise AttributeError("has_textual_implementation ausente")
        return self._has_textual_implementation

    def __repr__(self):
        raise AssertionError("repr proibido em FakeNode")

    def __str__(self):
        raise AssertionError("str proibido em FakeNode")


class FakeApplication(_ForbiddenApiMixin, object):
    """Raiz da subarvore (Application ja resolvida). Nao expoe indicadores
    tri-state (mesmo comportamento real ja observado: FakeApplication em
    test_read_only_text_exporter.py tambem nao expunha)."""

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


def _run(application, **kwargs):
    return inv_mod.GraphicLanguageInventory(**kwargs).inventory(application)


# =============================================================================
# ESTRUTURA / NAVEGACAO (paridade com scanner/exportador)
# =============================================================================

def test_application_without_children_produces_three_empty_artifacts():
    application = FakeApplication(children=[])
    result = _run(application)
    assert result["tree"]["node_id"] == "application"
    assert result["tree"]["children"] == []
    assert result["statistics"]["total_nodes"] == 1
    assert result["statistics"]["scan_complete"] is True

    flat = inv_mod.flatten_tree(result["tree"])
    by_state = inv_mod.split_by_state(flat)
    # so a raiz existe, e ela e 'unsupported' (Application nao expoe
    # has_textual_declaration -> indicator_unsupported -> nao confirmado True).
    assert len(flat) == 1
    assert sum(len(v) for v in by_state.values()) == 1


def test_multiple_levels_node_ids_prefixed_application():
    grandchild = FakeNode(name="Program", has_textual_declaration=False,
                          has_textual_implementation=False)
    child = FakeNode(name="Pou", has_textual_declaration=False,
                     has_textual_implementation=False, children=[grandchild])
    application = FakeApplication(children=[child])
    result = _run(application)
    child_node = result["tree"]["children"][0]
    assert child_node["node_id"] == "application/0"
    gc_node = child_node["children"][0]
    assert gc_node["node_id"] == "application/0/0"
    assert gc_node["depth"] == 2


def test_max_depth_limit_stops_expansion():
    n2 = FakeNode(name="L2", has_textual_declaration=False, has_textual_implementation=False)
    n1 = FakeNode(name="L1", has_textual_declaration=False, has_textual_implementation=False, children=[n2])
    application = FakeApplication(children=[n1])
    result = _run(application, max_depth=1)
    l1_node = _node_by_id(result["tree"], "application/0")
    assert l1_node["identity"]["name"]["value"] == "L1"
    l2_node = _node_by_id(result["tree"], "application/0/0")
    assert l2_node["collection"]["state"] == "not_attempted_depth_limit"
    assert result["limits"]["max_depth_reached"] is True


def test_max_children_per_node_limit():
    children = [FakeNode(name="N%d" % i, has_textual_declaration=False,
                         has_textual_implementation=False) for i in range(10)]
    application = FakeApplication(children=children)
    result = _run(application, max_children_per_node=5)
    assert result["tree"]["children"] == []
    assert result["tree"]["collection"]["state"] == "children_limit_exceeded"
    assert result["limits"]["max_children_per_node_reached"] is True


def test_max_total_nodes_limit_aborts_preserving_partial():
    def leaf(name):
        return FakeNode(name=name, has_textual_declaration=False, has_textual_implementation=False)

    branch_a = FakeNode(name="A", has_textual_declaration=False, has_textual_implementation=False,
                        children=[leaf("A%d" % i) for i in range(3)])
    branch_b = FakeNode(name="B", has_textual_declaration=False, has_textual_implementation=False,
                        children=[leaf("B%d" % i) for i in range(3)])
    application = FakeApplication(children=[branch_a, branch_b])
    result = _run(application, max_total_nodes=4)
    assert result["statistics"]["scan_complete"] is False
    assert result["limits"]["max_total_nodes_reached"] is True
    assert len(result["tree"]["children"]) == 2


def test_each_index_accessed_once():
    grandchildren = [FakeNode(name="G%d" % i, has_textual_declaration=False,
                              has_textual_implementation=False) for i in range(3)]
    collection = FakeCollection(grandchildren)
    child = FakeNode(name="Folder", has_textual_declaration=False,
                     has_textual_implementation=False, children_collection_override=collection)
    application = FakeApplication(children=[child])
    _run(application)
    assert collection.index_accesses == [0, 1, 2]


def test_collection_never_iterated_directly():
    children = [FakeNode(name="N%d" % i, has_textual_declaration=False,
                         has_textual_implementation=False) for i in range(4)]
    application = FakeApplication(children=children)
    result = _run(application)
    assert len(result["tree"]["children"]) == 4


# =============================================================================
# IDENTIDADE DA APPLICATION
# =============================================================================

def test_application_identity_mismatch_reported_but_does_not_abort_generic_class():
    application = FakeApplication(name="NotApplication")
    engine = inv_mod.GraphicLanguageInventory(expected_application_name="Application")
    result = engine.inventory(application)
    assert len(result["application_identity_mismatch"]) == 1
    mismatch = result["application_identity_mismatch"][0]
    assert mismatch["field"] == "name"
    assert mismatch["expected"] == "Application"
    assert mismatch["observed_value"] == "NotApplication"
    # a classe generica NAO aborta sozinha: quem decide abortar e o script
    # chamador (probe 14) — mesmo padrao ja usado por ReadOnlyTextExporter.
    assert result["statistics"]["scan_complete"] is True


def test_application_identity_matches_expected_no_mismatch():
    application = FakeApplication(name="Application")
    engine = inv_mod.GraphicLanguageInventory(
        expected_application_name="Application",
        expected_application_type_guid="639b491f-5557-464c-af91-1471bac9f549",
        expected_application_guid="00000000-0000-0000-0000-000000000001")
    result = engine.inventory(application)
    assert result["application_identity_mismatch"] == []


# =============================================================================
# CLASSIFICACAO — os 4 estados exigidos pelo roadmap
# =============================================================================

def test_classification_supported_declaration_and_implementation_confirmed():
    node = FakeNode(name="MainPrg", has_textual_declaration=True, has_textual_implementation=True)
    application = FakeApplication(children=[node])
    result = _run(application)
    child = result["tree"]["children"][0]
    assert child["state"] == "supported"
    assert result["statistics"]["state_counts"]["supported"] == 1


def test_classification_unsupported_no_declaration():
    folder = FakeNode(name="Folder", is_folder=True,
                      has_textual_declaration=False, has_textual_implementation=False)
    application = FakeApplication(children=[folder])
    result = _run(application)
    child = result["tree"]["children"][0]
    assert child["state"] == "unsupported"


def test_classification_unsupported_when_indicator_absent():
    # has_textual_declaration ausente (AttributeError) -> indicator_unsupported
    # -> nao confirmado True -> 'unsupported' (mesmo tratamento de "fora do
    # escopo de POU com corpo de logica").
    node = FakeNode(name="NoIndicator")
    application = FakeApplication(children=[node])
    result = _run(application)
    child = result["tree"]["children"][0]
    assert child["state"] == "unsupported"


def test_classification_partially_supported_shared_type_guid_with_implementation():
    shared_type = FakeGuidValue("shared-type-guid")
    supported_node = FakeNode(name="MainPrg", type_guid=shared_type,
                              has_textual_declaration=True, has_textual_implementation=True)
    candidate_node = FakeNode(name="StartPrg", type_guid=shared_type,
                              has_textual_declaration=True, has_textual_implementation=False)
    application = FakeApplication(children=[supported_node, candidate_node])
    result = _run(application)

    supported = _node_by_id(result["tree"], "application/0")
    candidate = _node_by_id(result["tree"], "application/1")
    assert supported["state"] == "supported"
    assert candidate["state"] == "partially_supported"
    assert "application/0" in candidate["evidence"]
    assert result["statistics"]["state_counts"]["partially_supported"] == 1


def test_classification_unknown_unique_type_guid_no_reference():
    node = FakeNode(name="LonelyPou", type_guid=FakeGuidValue("unique-type-guid"),
                    has_textual_declaration=True, has_textual_implementation=False)
    application = FakeApplication(children=[node])
    result = _run(application)
    child = result["tree"]["children"][0]
    assert child["state"] == "unknown"
    assert result["statistics"]["state_counts"]["unknown"] == 1


def test_classification_partially_supported_evidence_can_reference_later_sibling():
    """O no candidato aparece ANTES, na ordem de navegacao, do no que prova
    seu type_guid como familia com implementacao textual — a classificacao
    so pode rodar DEPOIS da arvore inteira construida (segunda passada)."""
    shared_type = FakeGuidValue("shared-type-guid-2")
    candidate_node = FakeNode(name="UserPrg", type_guid=shared_type,
                              has_textual_declaration=True, has_textual_implementation=False)
    supported_node = FakeNode(name="SpecialVariablesPrg", type_guid=shared_type,
                              has_textual_declaration=True, has_textual_implementation=True)
    application = FakeApplication(children=[candidate_node, supported_node])
    result = _run(application)

    candidate = _node_by_id(result["tree"], "application/0")
    assert candidate["state"] == "partially_supported"


def test_classification_indicator_raises_unexpected_exception_not_confirmed_true():
    node = FakeNode(name="Weird", has_declaration_raises=RuntimeError("boom"))
    application = FakeApplication(children=[node])
    result = _run(application)
    child = result["tree"]["children"][0]
    # has_textual_declaration NAO confirmado True (state == unknown) -> unsupported.
    assert child["indicators"]["has_textual_declaration"]["state"] == "unknown"
    assert child["state"] == "unsupported"


def test_classification_non_boolean_indicator_not_confirmed_true():
    node = FakeNode(name="NonBool", has_textual_declaration="yes")
    application = FakeApplication(children=[node])
    result = _run(application)
    child = result["tree"]["children"][0]
    assert child["indicators"]["has_textual_declaration"]["state"] == "not_boolean"
    assert child["state"] == "unsupported"


def test_never_reads_text_content():
    """Prova de nao-regressao de escopo: mesmo com indicadores True, o
    inventario NUNCA acessa .textual_declaration/.textual_implementation/
    .text (a bomba _TextAccessBomb explodiria com AssertionError)."""
    node = FakeNode(name="Pou1", has_textual_declaration=True, has_textual_implementation=True)
    application = FakeApplication(children=[node])
    _run(application)  # nao deve levantar AssertionError


# =============================================================================
# ARTEFATOS — subconjuntos exatos e consistentes
# =============================================================================

def test_split_by_state_is_exact_and_consistent_subset():
    shared_type = FakeGuidValue("shared-type-guid-3")
    supported_node = FakeNode(name="Supported", has_textual_declaration=True, has_textual_implementation=True)
    partial_node = FakeNode(name="Partial", type_guid=shared_type,
                            has_textual_declaration=True, has_textual_implementation=False)
    partial_ref = FakeNode(name="PartialRef", type_guid=shared_type,
                           has_textual_declaration=True, has_textual_implementation=True)
    unsupported_node = FakeNode(name="Unsupported", is_folder=True,
                                has_textual_declaration=False, has_textual_implementation=False)
    unknown_node = FakeNode(name="Unknown", has_textual_declaration=True, has_textual_implementation=False)

    application = FakeApplication(
        children=[supported_node, partial_node, partial_ref, unsupported_node, unknown_node])
    result = _run(application)

    flat = inv_mod.flatten_tree(result["tree"])
    by_state = inv_mod.split_by_state(flat)

    all_from_subsets = (by_state["supported"] + by_state["partially_supported"]
                        + by_state["unsupported"] + by_state["unknown"])
    # cada entrada de flat_nodes (exceto duplicatas por estado invalido, que
    # nao existem aqui) aparece em EXATAMENTE um subconjunto.
    flat_node_ids = sorted(e["node_id"] for e in flat)
    subset_node_ids = sorted(e["node_id"] for e in all_from_subsets)
    assert flat_node_ids == subset_node_ids

    # cada subconjunto so contem entradas com o state correspondente.
    for state_name, entries in by_state.items():
        for entry in entries:
            assert entry["state"] == state_name

    # 'Supported' (decl+impl confirmados) e 'PartialRef' (mesmo type_guid de
    # 'Partial', tambem com decl+impl confirmados) sao AMBOS 'supported'.
    assert len(by_state["supported"]) == 2
    assert len(by_state["partially_supported"]) == 1
    assert len(by_state["unknown"]) == 1
    # 'Unsupported' (indicadores confirmados False) + a Application raiz
    # (indicadores ausentes, nao confirmados True) -> 2 unsupported no total.
    assert len(by_state["unsupported"]) == 2

    unsupported_names = sorted(
        e["name"] for e in by_state["unsupported"] if e["name"] is not None)
    assert "Unsupported" in unsupported_names


# =============================================================================
# FALHAS ESTRUTURAIS ISOLADAS (paridade com scanner/exportador)
# =============================================================================

def test_root_get_children_failure_isolated():
    application = FakeApplication(get_children_raises=RuntimeError("boom"))
    result = _run(application)
    assert result["tree"]["collection"]["state"] == "unknown"
    assert result["tree"]["children"] == []
    assert any(e["where"] == "application" for e in result["errors"])


def test_partial_branch_does_not_abort_sibling_branches():
    broken = FakeNode(name="Broken", has_textual_declaration=False, has_textual_implementation=False,
                      get_children_raises=RuntimeError("boom"))
    healthy = FakeNode(name="Healthy", has_textual_declaration=False, has_textual_implementation=False,
                       children=[FakeNode(name="Grandchild", has_textual_declaration=False,
                                          has_textual_implementation=False)])
    application = FakeApplication(children=[broken, healthy])
    result = _run(application)
    broken_node = _node_by_id(result["tree"], "application/0")
    healthy_node = _node_by_id(result["tree"], "application/1")
    assert broken_node["collection"]["state"] == "unknown"
    assert len(healthy_node["children"]) == 1
    assert result["statistics"]["total_nodes"] == 4
    # falha isolada de colecao nao impede a CLASSIFICACAO do proprio no.
    assert broken_node["state"] == "unsupported"


def test_indexer_failure_stops_only_that_collection():
    def leaf(name):
        return FakeNode(name=name, has_textual_declaration=False, has_textual_implementation=False)

    collection = FakeCollection([leaf("OK0"), leaf("OK1"), leaf("OK2")], fail_at_index=1)
    child = FakeNode(name="Parent", has_textual_declaration=False, has_textual_implementation=False,
                     children_collection_override=collection)
    application = FakeApplication(children=[child])
    result = _run(application)
    node = result["tree"]["children"][0]
    assert len(node["children"]) == 1
    assert node["collection"]["state"] == "partial_indexing"


def test_identity_field_failure_isolated_but_node_still_present():
    node = FakeNode(name="BadType", type_raises=RuntimeError("boom"),
                    has_textual_declaration=True, has_textual_implementation=False)
    application = FakeApplication(children=[node])
    result = _run(application)
    child = result["tree"]["children"][0]
    assert child["identity"]["type_guid"]["state"] == "unknown"
    # sem type_guid confirmado, nunca pode ser partially_supported (sem
    # chave para comparar) -> cai em 'unknown'.
    assert child["state"] == "unknown"


# =============================================================================
# SEGURANCA — APIs proibidas nunca chamadas; sem proxies no resultado
# =============================================================================

def test_forbidden_apis_never_called():
    node = FakeNode(name="Guarded", has_textual_declaration=True, has_textual_implementation=True)
    application = FakeApplication(children=[node])
    _run(application)  # FakeNode/_ForbiddenApiMixin levantaria AssertionError se chamado


def test_no_proxy_leaks_into_serialized_result():
    node = FakeNode(name="Pou1", has_textual_declaration=True, has_textual_implementation=True)
    application = FakeApplication(children=[node])
    result = _run(application)
    for leaf in _walk_leaves(result):
        assert not isinstance(leaf, (FakeApplication, FakeNode, FakeCollection, _TextAccessBomb))
        assert isinstance(leaf, (str, int, float, bool, type(None)))


def test_safety_declaration_fields():
    application = FakeApplication(children=[])
    result = _run(application)
    decl = result["safety_declaration"]
    assert decl["read_only"] is True
    assert decl["text_content_read"] is False
    assert decl["textual_declaration_text_accessed"] is False
    assert decl["textual_implementation_text_accessed"] is False
    assert decl["new_member_probing"] is False
    for key in ("project_write", "project_save", "project_close", "object_creation",
               "object_modification", "find_used", "compilation", "online_access",
               "device_repository_access", "device_configuration_access",
               "download", "force", "collection_direct_iteration"):
        assert decl[key] is False


def test_unknown_identity_object_with_exploding_repr_handled_safely():
    node = FakeNode(type_guid=UnknownBombValue(), object_guid=UnknownBombValue(),
                    has_textual_declaration=False, has_textual_implementation=False)
    application = FakeApplication(children=[node])
    result = _run(application)
    identity = result["tree"]["children"][0]["identity"]
    assert identity["type_guid"]["state"] == "unrepresentable"
    assert identity["object_guid"]["state"] == "unrepresentable"


# =============================================================================
# DRY-RUN / DEGRADACAO GRACIOSA (externo ao MasterTool)
# =============================================================================

def test_dry_run_without_projects_available_degrades_gracefully():
    """Mesmo padrao de todos os probes anteriores: sem 'projects' no
    ScriptEngine, o wrapper (nao a classe pura) deve produzir um relatorio
    vazio, sem excecao. Aqui testamos a camada pura equivalente: nenhum
    'application' resolvido significa que inventory() simplesmente nunca e
    chamado — o comportamento gracioso vive no script probe (fora do escopo
    unitario desta classe), mas garantimos que a classe pura, quando NAO
    invocada, nao deixa nenhum estado pendente (sem side effects globais)."""
    # A classe pura nao tem estado de modulo compartilhado: instancia-la sem
    # nunca chamar .inventory() nao deve ter nenhum efeito colateral.
    engine = inv_mod.GraphicLanguageInventory()
    assert engine.max_depth == inv_mod.DEFAULT_MAX_DEPTH
    assert engine.max_total_nodes == inv_mod.DEFAULT_MAX_TOTAL_NODES
    assert engine.max_children_per_node == inv_mod.DEFAULT_MAX_CHILDREN_PER_NODE


# =============================================================================
# DETERMINISMO
# =============================================================================

def test_deterministic_output_same_tree_twice():
    def build_tree():
        shared_type = FakeGuidValue("shared-type-guid-det")
        supported_node = FakeNode(name="Supported", has_textual_declaration=True, has_textual_implementation=True)
        partial_node = FakeNode(name="Partial", type_guid=shared_type,
                                has_textual_declaration=True, has_textual_implementation=False)
        partial_ref = FakeNode(name="PartialRef", type_guid=shared_type,
                               has_textual_declaration=True, has_textual_implementation=True)
        return FakeApplication(children=[supported_node, partial_node, partial_ref])

    result_1 = _run(build_tree())
    result_2 = _run(build_tree())

    flat_1 = inv_mod.flatten_tree(result_1["tree"])
    flat_2 = inv_mod.flatten_tree(result_2["tree"])

    def _strip_guids(entries):
        # GUIDs sao gerados de forma sequencial-mas-unica pelos fakes; o que
        # importa para determinismo e a FORMA (ordem, nomes, estados), nao o
        # valor exato do GUID (que so precisa ser estavel DENTRO de uma
        # execucao, nao entre execucoes distintas do mesmo fake builder).
        stripped = []
        for e in entries:
            copy = dict(e)
            copy.pop("object_guid", None)
            copy.pop("type_guid", None)
            stripped.append(copy)
        return stripped

    assert _strip_guids(flat_1) == _strip_guids(flat_2)
    assert result_1["statistics"]["state_counts"] == result_2["statistics"]["state_counts"]

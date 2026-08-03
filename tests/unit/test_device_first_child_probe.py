"""Testa common/device_first_child_probe.py (identidade do primeiro filho de
Device, segundo nivel de navegacao apos o probe 09).

Motivo (2026-07-23): aprovado o probe 10 (acessar SOMENTE
device_children[0], sem misturar com active_application), o usuario pediu
testes PERMANENTES persistidos ANTES da execucao real, cobrindo: sucesso
completo, raiz com Count != 4, identidade de Device divergente, filhos de
Device com Count != 2, colecao sem interface de contagem, falha no
indexador 0, falha isolada em cada campo de identidade, garantia de que o
indice 1 nunca e acessado, e garantia de que o primeiro filho nao recebe
get_children(). Usa fakes em memoria (sem MasterTool real), mesmo padrao
de tests/unit/test_project_tree_adapter.py.
"""

import sys
from pathlib import Path

SCRIPTS_MASTERTOOL = Path(__file__).resolve().parents[2] / "scripts" / "mastertool"
if str(SCRIPTS_MASTERTOOL) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_MASTERTOOL))

from common import device_first_child_probe as dfcp  # noqa: E402

EXPECTED_DEVICE_TYPE_GUID = "225bfe47-7336-4dbc-9419-4105a7c831fa"
EXPECTED_DEVICE_OBJECT_GUID = "ec2ca054-836f-492f-a95f-f296c4785352"


class FakeClrTypeInfo(object):
    """Simula o retorno de value.GetType() só para dotnet_type_info()
    (expõe .FullName). Não confunda com FakeClrTypeForInterfaces abaixo."""
    def __init__(self, full_name):
        self.FullName = full_name


class FakeGuidValue(object):
    """Simula um valor CONFIRMADO como System.Guid via GetType()."""
    def __init__(self, text):
        self._text = text

    def GetType(self):
        return FakeClrTypeInfo("System.Guid")

    def __str__(self):
        return self._text

    def __repr__(self):
        raise AssertionError("repr() nao deveria ser chamado")


class FakeClrInterface(object):
    def __init__(self, name):
        self.Name = name


class FakeClrTypeForInterfaces(object):
    """GetType() usado por _implements_count_bearing_interface() — expõe
    GetInterfaces(), distinto de FakeClrTypeInfo (usado por dotnet_type_info,
    que só lê .FullName). Uma colecao real precisa responder aos dois."""
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
        raise AssertionError("colecao NAO deve ser iterada pelo probe")


class FakeFirstChild(object):
    def __init__(self, name="Application", is_folder=False,
                type_value=None, guid_value=None,
                name_raises=None, is_folder_raises=None,
                type_raises=None, guid_raises=None):
        self._name = name
        self._is_folder = is_folder
        self._type_value = type_value if type_value is not None else FakeGuidValue("type-guid-child0")
        self._guid_value = guid_value if guid_value is not None else FakeGuidValue("object-guid-child0")
        self._name_raises = name_raises
        self._is_folder_raises = is_folder_raises
        self._type_raises = type_raises
        self._guid_raises = guid_raises
        self.get_children_calls = 0

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
        return self._type_value

    @property
    def guid(self):
        if self._guid_raises is not None:
            raise self._guid_raises
        return self._guid_value

    def get_children(self, recursive):
        # NUNCA deve ser chamado pelo probe — se for, o teste que conta
        # get_children_calls vai flagar.
        self.get_children_calls += 1
        return FakeCollection([])


class FakeDevice(object):
    def __init__(self, name="Device", type_guid=None, object_guid=None,
                children_collection=None, get_children_raises=None):
        self._name = name
        self._type_guid = type_guid if type_guid is not None else FakeGuidValue(EXPECTED_DEVICE_TYPE_GUID)
        self._object_guid = object_guid if object_guid is not None else FakeGuidValue(EXPECTED_DEVICE_OBJECT_GUID)
        self._children_collection = (children_collection if children_collection is not None
                                     else FakeCollection([FakeFirstChild(), FakeFirstChild(name="Outro")]))
        self._get_children_raises = get_children_raises
        self.get_children_calls = 0

    def get_name(self, recursive):
        return self._name

    @property
    def type(self):
        return self._type_guid

    @property
    def guid(self):
        return self._object_guid

    def get_children(self, recursive):
        self.get_children_calls += 1
        if self._get_children_raises is not None:
            raise self._get_children_raises
        return self._children_collection


class FakeProject(object):
    def __init__(self, root_count=4, device=None):
        self._device = device or FakeDevice()
        self._children = FakeCollection(
            [object(), self._device, object(), object()], count_value=root_count)

    def get_children(self, recursive):
        return self._children


def _happy_device():
    first_child = FakeFirstChild(name="Application", is_folder=False)
    second_child = FakeFirstChild(name="Bus")
    children = FakeCollection([first_child, second_child], count_value=2)
    return FakeDevice(children_collection=children), first_child, children


# --- 1. sucesso completo ------------------------------------------------------
def test_full_success():
    device, first_child, device_children = _happy_device()
    project = FakeProject(root_count=4, device=device)
    result = dfcp.probe_device_first_child(project)

    assert result["complete"] is True
    assert result["errors"] == []
    rv = result["root_validation"]
    assert rv["count"] == 4
    assert rv["device_identity_confirmed"] is True
    dc = result["device_collection"]
    assert dc["count"] == 2
    assert dc["count_matches_expected"] is True
    ea = result["element_access"]
    assert ea["state"] == "confirmed"
    assert ea["index"] == 0
    fc = result["first_child"]
    assert fc["name"]["state"] == "confirmed" and fc["name"]["value"] == "Application"
    assert fc["is_folder"]["state"] == "confirmed" and fc["is_folder"]["value"] is False
    assert fc["type"]["state"] == "confirmed" and fc["type"]["value"] == "type-guid-child0"
    assert fc["guid"]["state"] == "confirmed" and fc["guid"]["value"] == "object-guid-child0"


# --- 2. raiz com quantidade diferente de 4 ------------------------------------
def test_root_count_mismatch_aborts_before_index_access():
    device, _, _ = _happy_device()
    project = FakeProject(root_count=3, device=device)
    result = dfcp.probe_device_first_child(project)

    assert result["complete"] is False
    assert result["root_validation"]["count_matches_expected"] is False
    assert result["root_validation"]["element_access_state"] is None
    assert device.get_children_calls == 0
    assert any("root_count_mismatch" in e["message"] for e in result["errors"])


# --- 3. identidade de Device divergente ---------------------------------------
def test_device_identity_mismatch_name_aborts_before_device_get_children():
    device = FakeDevice(name="NomeErrado")
    project = FakeProject(root_count=4, device=device)
    result = dfcp.probe_device_first_child(project)

    assert result["complete"] is False
    assert result["root_validation"]["device_identity_confirmed"] is False
    assert device.get_children_calls == 0
    assert any("device_identity_mismatch" in e["message"] for e in result["errors"])


def test_device_identity_mismatch_type_guid_aborts():
    device = FakeDevice(type_guid=FakeGuidValue("guid-errado"))
    project = FakeProject(root_count=4, device=device)
    result = dfcp.probe_device_first_child(project)

    assert result["root_validation"]["device_identity"]["type_guid"]["matches_expected"] is False
    assert result["root_validation"]["device_identity_confirmed"] is False
    assert device.get_children_calls == 0


# --- 4. quantidade de filhos de Device diferente de 2 -------------------------
def test_device_children_count_mismatch_aborts_before_index_0():
    children = FakeCollection([FakeFirstChild(), FakeFirstChild(), FakeFirstChild()], count_value=3)
    device = FakeDevice(children_collection=children)
    project = FakeProject(root_count=4, device=device)
    result = dfcp.probe_device_first_child(project)

    assert result["complete"] is False
    assert result["device_collection"]["count_matches_expected"] is False
    assert result["element_access"]["attempted"] is False
    assert children.index_accesses == []
    assert any("device_children_count_mismatch" in e["message"] for e in result["errors"])


# --- 5. colecao de filhos de Device sem interface de contagem -----------------
def test_device_children_without_count_interface_aborts():
    children = FakeCollection([FakeFirstChild(), FakeFirstChild()], count_value=2, implements=False)
    device = FakeDevice(children_collection=children)
    project = FakeProject(root_count=4, device=device)
    result = dfcp.probe_device_first_child(project)

    assert result["complete"] is False
    assert result["device_collection"]["implements_count_bearing_interface"] is False
    assert result["element_access"]["attempted"] is False
    assert children.index_accesses == []
    assert any("device_children_count_interface_unconfirmed" in e["message"] for e in result["errors"])


# --- 6. falha no indexador 0 ---------------------------------------------------
def test_indexer_zero_failure_aborts():
    children = FakeCollection([FakeFirstChild(), FakeFirstChild()], count_value=2,
                              fail_at_index=0, fail_exception=RuntimeError("boom"))
    device = FakeDevice(children_collection=children)
    project = FakeProject(root_count=4, device=device)
    result = dfcp.probe_device_first_child(project)

    assert result["complete"] is False
    assert result["element_access"]["state"] != "confirmed"
    assert any("device_children[0]" in e["where"] for e in result["errors"])


# --- 7. falha isolada em cada campo de identidade do primeiro filho -----------
def test_isolated_name_failure_does_not_block_other_fields():
    broken_child = FakeFirstChild(name_raises=RuntimeError("get_name explodiu"))
    children = FakeCollection([broken_child, FakeFirstChild()], count_value=2)
    device = FakeDevice(children_collection=children)
    project = FakeProject(root_count=4, device=device)
    result = dfcp.probe_device_first_child(project)

    assert result["complete"] is True
    fc = result["first_child"]
    assert fc["name"]["state"] == "unknown"
    assert fc["name"]["value"] is None
    assert fc["is_folder"]["state"] == "confirmed"
    assert fc["type"]["state"] == "confirmed"
    assert fc["guid"]["state"] == "confirmed"


def test_isolated_is_folder_failure_does_not_block_other_fields():
    broken_child = FakeFirstChild(is_folder_raises=RuntimeError("is_folder explodiu"))
    children = FakeCollection([broken_child, FakeFirstChild()], count_value=2)
    device = FakeDevice(children_collection=children)
    project = FakeProject(root_count=4, device=device)
    result = dfcp.probe_device_first_child(project)

    fc = result["first_child"]
    assert fc["is_folder"]["state"] == "unknown"
    assert fc["is_folder"]["value"] is None
    assert fc["name"]["state"] == "confirmed"
    assert fc["type"]["state"] == "confirmed"
    assert fc["guid"]["state"] == "confirmed"


def test_isolated_type_failure_and_absent_guid_do_not_block_other_fields():
    broken_child = FakeFirstChild(type_raises=RuntimeError("type explodiu"),
                                  guid_raises=AttributeError("guid ausente"))
    children = FakeCollection([broken_child, FakeFirstChild()], count_value=2)
    device = FakeDevice(children_collection=children)
    project = FakeProject(root_count=4, device=device)
    result = dfcp.probe_device_first_child(project)

    fc = result["first_child"]
    assert fc["type"]["state"] == "unknown"
    assert fc["type"]["value"] is None
    assert fc["guid"]["state"] == "unsupported"
    assert fc["guid"]["value"] is None
    assert fc["name"]["state"] == "confirmed"
    assert fc["is_folder"]["state"] == "confirmed"


def test_type_guid_value_only_serialized_when_confirmed_system_guid():
    # type/guid retornam algo que NAO foi confirmado como System.Guid (aqui,
    # um objeto sem GetType() nenhum) — deve ficar sem valor, mesmo tendo
    # sido obtido com sucesso via getattr.
    class NotAGuid(object):
        def __repr__(self):
            raise AssertionError("repr() nao deveria ser chamado")

    child = FakeFirstChild(type_value=NotAGuid(), guid_value=NotAGuid())
    children = FakeCollection([child, FakeFirstChild()], count_value=2)
    device = FakeDevice(children_collection=children)
    project = FakeProject(root_count=4, device=device)
    result = dfcp.probe_device_first_child(project)

    fc = result["first_child"]
    assert fc["type"]["state"] == "confirmed_not_guid"
    assert fc["type"]["value"] is None
    assert fc["guid"]["state"] == "confirmed_not_guid"
    assert fc["guid"]["value"] is None
    # o restante do snapshot continua completo — isto NAO e uma falha fatal.
    assert result["complete"] is True


# --- 8. garantia de que o indice 1 (de Device.children) nunca e acessado -----
def test_index_one_of_device_children_never_accessed():
    device, first_child, device_children = _happy_device()
    project = FakeProject(root_count=4, device=device)
    dfcp.probe_device_first_child(project)
    assert device_children.index_accesses == [0]


def test_root_index_other_than_one_never_accessed():
    device, _, _ = _happy_device()
    project = FakeProject(root_count=4, device=device)
    dfcp.probe_device_first_child(project)
    assert project._children.index_accesses == [1]


# --- 9. garantia de que o primeiro filho nao recebe get_children() -----------
def test_first_child_never_receives_get_children_call():
    first_child = FakeFirstChild(name="Application")
    device_children = FakeCollection([first_child, FakeFirstChild(name="Bus")], count_value=2)
    device = FakeDevice(children_collection=device_children)
    project = FakeProject(root_count=4, device=device)
    dfcp.probe_device_first_child(project)
    assert first_child.get_children_calls == 0


# --- extra: falhas estruturais mais cedo na cadeia -----------------------------
def test_root_get_children_failure_aborts():
    class BrokenProject(object):
        def get_children(self, recursive):
            raise RuntimeError("get_children explodiu")

    result = dfcp.probe_device_first_child(BrokenProject())
    assert result["complete"] is False
    assert result["root_validation"]["get_children_state"] == "unknown"
    assert any(e["where"] == "get_children" for e in result["errors"])


def test_device_get_children_collection_null_aborts():
    class NullReturningDevice(FakeDevice):
        def get_children(self, recursive):
            self.get_children_calls += 1
            return None

    device = NullReturningDevice()
    project = FakeProject(root_count=4, device=device)
    result = dfcp.probe_device_first_child(project)
    assert result["complete"] is False
    assert result["device_collection"]["is_null"] is True
    assert result["element_access"]["attempted"] is False

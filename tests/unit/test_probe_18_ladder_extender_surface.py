"""Testa scripts/mastertool/probes/18_probe_ladder_extender_surface.py EM
ISOLAMENTO (lado IronPython 2.7, roda DENTRO do MasterTool) -- Fase L1
(docs/14-ladder-roadmap.md), IRMAO de test_probe_17_ladder_dynamic_surface.py.

Mesma filosofia de dubles (fakes) que os testes dos probes 16/17: nenhum
proxy CLR real, so o suficiente para exercitar navegacao bounded/indexada +
identidade + reflexao do membro 'Extender' + inspecao do objeto Extender +
canal ICustomTypeDescriptor + classificacao de candidatos.

Carregamento do modulo: o arquivo comeca com digito ('18_...'), entao
'import probes.18_probe...' e SyntaxError -- e preciso carregar pelo
CAMINHO, mesmo mecanismo usado por test_probe_17_ladder_dynamic_surface.py
(tentar importlib.util, cair para imp so em IronPython 2.7).
"""

import json
import os
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_MASTERTOOL = REPO_ROOT / "scripts" / "mastertool"
PROBE_PATH = SCRIPTS_MASTERTOOL / "probes" / "18_probe_ladder_extender_surface.py"

if str(SCRIPTS_MASTERTOOL) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_MASTERTOOL))


def _load_probe_module():
    module_name = "mastertool_bridge_probe_18_ladder_extender_surface"
    try:
        import importlib.util as _importlib_util
    except ImportError:
        _importlib_util = None

    if _importlib_util is not None and hasattr(_importlib_util, "spec_from_file_location"):
        spec = _importlib_util.spec_from_file_location(module_name, str(PROBE_PATH))
        if spec is None or spec.loader is None:
            raise ImportError("nao foi possivel montar o spec do probe 18: %s" % PROBE_PATH)
        module = _importlib_util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module

    import imp  # IronPython 2.7: unico mecanismo disponivel
    return imp.load_source(module_name, str(PROBE_PATH))


probe_mod = _load_probe_module()


# =============================================================================
# Dubles (fakes) -- proxies CLR minimos.
# =============================================================================

class FakeAssembly(object):
    def __init__(self, full_name):
        self.FullName = full_name


class FakeTypeRef(object):
    """Representa um System.Type -- usado tanto para tipos de retorno quanto
    para o proprio GetType() de um objeto, quando o objeto so precisa expor
    metadados (nunca invocado como instancia real)."""

    def __init__(self, full_name, assembly_full_name="TestAssembly, Version=1.0.0.0",
                interfaces=None, properties=None, methods=None, fields=None, events=None,
                is_array=False, assembly_qualified_name=None):
        self.FullName = full_name
        self.Assembly = FakeAssembly(assembly_full_name)
        self.AssemblyQualifiedName = assembly_qualified_name or (full_name + ", " + assembly_full_name)
        self._interfaces = interfaces or []
        self._properties = properties or []
        self._methods = methods or []
        self._fields = fields or []
        self._events = events or []
        self.IsArray = is_array

    def GetInterfaces(self):
        return self._interfaces

    def GetProperties(self):
        return self._properties

    def GetMethods(self):
        return self._methods

    def GetFields(self):
        return self._fields

    def GetEvents(self):
        return self._events


class FakeInterfaceInfo(object):
    def __init__(self, full_name, assembly_full_name="TestAssembly, Version=1.0.0.0"):
        self.FullName = full_name
        self.Assembly = FakeAssembly(assembly_full_name)


class FakeFieldInfo(object):
    def __init__(self, name):
        self.Name = name


class FakeEventInfo(object):
    def __init__(self, name):
        self.Name = name


class FakePropertyInfo(object):
    def __init__(self, name, declaring_type_name, return_type_name, can_read=True,
                has_index_parameters=False):
        self.Name = name
        self.DeclaringType = FakeTypeRef(declaring_type_name)
        self.PropertyType = FakeTypeRef(return_type_name)
        self.CanRead = can_read
        self._has_index_parameters = has_index_parameters

    def GetIndexParameters(self):
        return [object()] if self._has_index_parameters else []


class FakeParameterInfo(object):
    def __init__(self, name, type_name):
        self.Name = name
        self.ParameterType = FakeTypeRef(type_name)


class FakeMethodInfo(object):
    def __init__(self, name, declaring_type_name, return_type_name, parameters=None,
                is_special_name=False, is_public=True):
        self.Name = name
        self.DeclaringType = FakeTypeRef(declaring_type_name)
        self.ReturnType = FakeTypeRef(return_type_name)
        self.IsSpecialName = is_special_name
        self.IsPublic = is_public
        self._parameters = parameters or []

    def GetParameters(self):
        return self._parameters


class FakeChildrenCollection(object):
    """Colecao bounded: expoe Count + indexador nativo, NUNCA iteracao
    direta -- o probe so pode navegar via esses dois membros."""

    def __init__(self, items):
        self._items = list(items)

    @property
    def Count(self):
        return len(self._items)

    def __getitem__(self, index):
        return self._items[index]


TARGET_NAME = "BLINK_QUE_FUNCIONA"
TARGET_GUID = "beca53e2-8466-404a-baf5-9fba1adc0fac"
TARGET_TYPE_GUID = "6f9dac99-8de1-4efc-8465-68ac443b7d08"


class FakeNode(object):
    """Proxy CLR minimo do alvo. `clr_type` e o que GetType() enxerga -- deve
    incluir uma FakePropertyInfo('Extender', ...) para que a reflexao do
    probe encontre o membro. `extra_properties` mapeia nomes -> valor (ou
    excecao) devolvidos por getattr -- e como o Extender de fato e
    invocado."""

    def __init__(self, name, type_guid, object_guid, is_folder, children=None, clr_type=None,
                extra_properties=None):
        self._name = name
        self._type_guid = type_guid
        self._object_guid = object_guid
        self._is_folder = is_folder
        self._children = children or []
        self._clr_type = clr_type
        self._extra_properties = extra_properties or {}
        self.text_accessed = False

    def get_name(self, recursive):
        return self._name

    @property
    def type(self):
        return self._type_guid

    @property
    def guid(self):
        return self._object_guid

    @property
    def is_folder(self):
        return self._is_folder

    def get_children(self, recursive):
        return FakeChildrenCollection(self._children)

    def GetType(self):
        if self._clr_type is None:
            raise AssertionError(
                "GetType() nao deveria ser chamado neste teste (identidade nao "
                "confirmada ou clr_type nao configurado).")
        return self._clr_type

    @property
    def text(self):
        # Nunca deveria ser acessado por este probe.
        self.text_accessed = True
        return "NUNCA DEVERIA SER LIDO"

    def __getattr__(self, name):
        if name in self._extra_properties:
            value = self._extra_properties[name]
            if isinstance(value, Exception):
                raise value
            return value
        raise AttributeError(name)

    def __str__(self):
        raise AssertionError("str() NUNCA deveria ser chamado sobre o proxy-alvo.")

    def __repr__(self):
        raise AssertionError("repr() NUNCA deveria ser chamado sobre o proxy-alvo.")


def _base_ladder_probe_config(target_node_id="application/0/1"):
    return {
        "target_node_id": target_node_id,
        "expected_name": TARGET_NAME,
        "expected_guid": TARGET_GUID,
        "expected_type_guid": TARGET_TYPE_GUID,
    }


def _application_with_target(target_node):
    """application/0/1 -> target_node (2 niveis, navegacao bounded)."""
    sibling = FakeNode(name="Outro", type_guid="x", object_guid="y", is_folder=False)
    intermediate = FakeNode(
        name="Pasta", type_guid="folder-type", object_guid="folder-guid", is_folder=True,
        children=[sibling, target_node])
    application = FakeNode(
        name="Application", type_guid="app-type", object_guid="app-guid", is_folder=False,
        children=[intermediate])
    return application


def _extender_property(return_type_name="Vendor.Extension.ExtenderObject"):
    return FakePropertyInfo("Extender", "Vendor.ScriptEngine.ScriptObject", return_type_name)


class FakePropertyDescriptor(object):
    """PropertyDescriptor minimo: so os 4 campos autorizados pelo contrato
    (Name/PropertyType/ComponentType/IsReadOnly). GetValue/SetValue/
    ResetValue/AddValueChanged/RemoveValueChanged levantam se chamados --
    NENHUM caminho do probe deveria toca-los."""

    def __init__(self, name, property_type_name="System.String",
                component_type_name="Vendor.Extension.ExtenderObject", is_read_only=True,
                clr_type=None):
        self.Name = name
        self.PropertyType = FakeTypeRef(property_type_name)
        self.ComponentType = FakeTypeRef(component_type_name)
        self.IsReadOnly = is_read_only
        self._clr_type = clr_type or FakeTypeRef("Vendor.Extension.DynamicPropertyDescriptor")

    def GetType(self):
        return self._clr_type

    def GetValue(self, *a, **k):
        raise AssertionError("GetValue() NUNCA deveria ser chamado.")

    def SetValue(self, *a, **k):
        raise AssertionError("SetValue() NUNCA deveria ser chamado.")

    def ResetValue(self, *a, **k):
        raise AssertionError("ResetValue() NUNCA deveria ser chamado.")

    def AddValueChanged(self, *a, **k):
        raise AssertionError("AddValueChanged() NUNCA deveria ser chamado.")

    def RemoveValueChanged(self, *a, **k):
        raise AssertionError("RemoveValueChanged() NUNCA deveria ser chamado.")

    def __str__(self):
        raise AssertionError("str() NUNCA deveria ser chamado sobre um PropertyDescriptor.")

    def __repr__(self):
        raise AssertionError("repr() NUNCA deveria ser chamado sobre um PropertyDescriptor.")


class FakePropertyDescriptorCollection(object):
    """Colecao bounded (Count + indexador) que TAMBEM confirma, via
    GetType().GetInterfaces(), implementar uma interface de colecao
    conhecida (IList) -- exigido pelo contrato antes de qualquer
    enumeracao."""

    def __init__(self, items, implements_known_interface=True):
        self._items = list(items)
        interfaces = (
            [FakeInterfaceInfo("System.Collections.IList")]
            if implements_known_interface else [FakeInterfaceInfo("System.Collections.IEnumerable")])
        self._clr_type = FakeTypeRef(
            "System.ComponentModel.PropertyDescriptorCollection", interfaces=interfaces)

    @property
    def Count(self):
        return len(self._items)

    def __getitem__(self, index):
        return self._items[index]

    def GetType(self):
        return self._clr_type


class FakeExtenderObject(object):
    """Objeto retornado pelo getter 'Extender'. `descriptors` (se dado) faz
    GetProperties() (metodo ICustomTypeDescriptor) devolver uma colecao
    bounded de FakePropertyDescriptor -- SO chamado pelo probe se
    'ICustomTypeDescriptor' estiver entre as interfaces refletidas."""

    def __init__(self, clr_type, descriptors=None, get_properties_raises=None,
                collection_implements_known_interface=True):
        self._clr_type = clr_type
        self._descriptors = descriptors
        self._get_properties_raises = get_properties_raises
        self._collection_implements_known_interface = collection_implements_known_interface

    def GetType(self):
        return self._clr_type

    def GetProperties(self):
        if self._get_properties_raises is not None:
            raise self._get_properties_raises
        if self._descriptors is None:
            return None
        return FakePropertyDescriptorCollection(
            self._descriptors, implements_known_interface=self._collection_implements_known_interface)

    def GetMetaObject(self, *a, **k):
        raise AssertionError("GetMetaObject() NUNCA deveria ser chamado.")

    def CanExtend(self, *a, **k):
        raise AssertionError("CanExtend() NUNCA deveria ser chamado.")

    def __str__(self):
        raise AssertionError("str() NUNCA deveria ser chamado sobre o Extender.")

    def __repr__(self):
        raise AssertionError("repr() NUNCA deveria ser chamado sobre o Extender.")


def _clr_type_with_extender(extra_properties=None, extra_methods=None):
    properties = [_extender_property()]
    if extra_properties:
        properties.extend(extra_properties)
    methods = list(extra_methods or [])
    return FakeTypeRef("Vendor.ScriptEngine.ScriptObjectProxy",
                       properties=properties, methods=methods)


def _confirmed_target_node(clr_type, extender_value=None, extra_properties=None):
    props = dict(extra_properties or {})
    if extender_value is not None:
        props["Extender"] = extender_value
    return FakeNode(
        name=TARGET_NAME, type_guid=TARGET_TYPE_GUID, object_guid=TARGET_GUID,
        is_folder=False, clr_type=clr_type, extra_properties=props)


def _ctd_extender_type(extra_interfaces=None, extra_methods=None):
    interfaces = [FakeInterfaceInfo("System.ComponentModel.ICustomTypeDescriptor")]
    interfaces.extend(extra_interfaces or [])
    methods = [
        FakeMethodInfo("GetProperties", "Vendor.Extension.ExtenderObject",
                       "System.ComponentModel.PropertyDescriptorCollection"),
    ]
    methods.extend(extra_methods or [])
    return FakeTypeRef(
        "Vendor.Extension.ExtenderObject", interfaces=interfaces, methods=methods,
        properties=[], fields=[FakeFieldInfo("_cache")], events=[FakeEventInfo("Changed")])


# =============================================================================
# 1. E4 -- 'Extender' inacessivel (nao encontrado / getter invalido / falha
#    de invocacao / retorno nulo).
# =============================================================================

def test_case_E4_when_extender_member_not_reflected(tmp_path):
    clr_type = FakeTypeRef("Vendor.ScriptEngine.ScriptObjectProxy", properties=[], methods=[])
    target = _confirmed_target_node(clr_type)
    application = _application_with_target(target)
    config = _base_ladder_probe_config()

    result = probe_mod.probe_ladder_extender_surface(application, config, str(tmp_path))

    assert result["aborted"] is False
    assert result["result_case"] == "E4"
    assert result["status"] == "inconclusive"
    assert result["extender_accessible"] is False
    assert result["extender_channel_validated"] is False

    member = json.loads((tmp_path / "extender-member.json").read_text(encoding="utf-8"))
    assert member["found"] is False
    assert member["invocation_authorized"] is False


def test_case_E4_when_extender_getter_invocation_raises(tmp_path):
    clr_type = _clr_type_with_extender()
    target = _confirmed_target_node(
        clr_type, extra_properties={"Extender": RuntimeError("falha simulada de leitura")})
    application = _application_with_target(target)
    config = _base_ladder_probe_config()

    result = probe_mod.probe_ladder_extender_surface(application, config, str(tmp_path))

    assert result["result_case"] == "E4"
    assert result["status"] == "inconclusive"
    assert result["extender_accessible"] is False


def test_case_E4_when_extender_returns_null(tmp_path):
    clr_type = _clr_type_with_extender()
    target = _confirmed_target_node(clr_type, extender_value=None)
    application = _application_with_target(target)
    config = _base_ladder_probe_config()

    result = probe_mod.probe_ladder_extender_surface(application, config, str(tmp_path))

    assert result["result_case"] == "E4"
    assert result["extender_accessible"] is False


def test_case_E4_when_extender_property_has_no_getter(tmp_path):
    """CanRead=False -- reflexao NAO autoriza invocacao (guarda ANTES da
    chamada). O Extender fake nao seria sequer acessado se o probe tentasse
    invocar por engano."""
    bad_property = FakePropertyInfo(
        "Extender", "Vendor.ScriptEngine.ScriptObject", "Vendor.Extension.ExtenderObject",
        can_read=False)
    clr_type = FakeTypeRef(
        "Vendor.ScriptEngine.ScriptObjectProxy", properties=[bad_property], methods=[])
    target = _confirmed_target_node(
        clr_type, extra_properties={"Extender": RuntimeError("NUNCA deveria ser chamado")})
    application = _application_with_target(target)
    config = _base_ladder_probe_config()

    result = probe_mod.probe_ladder_extender_surface(application, config, str(tmp_path))

    assert result["result_case"] == "E4"
    member = json.loads((tmp_path / "extender-member.json").read_text(encoding="utf-8"))
    assert member["found"] is True
    assert member["invocation_authorized"] is False


# =============================================================================
# 2. E3 -- 'Extender' acessivel, canal NAO validado (todas as variantes).
# =============================================================================

def test_case_E3_reflection_without_extension_mechanism(tmp_path):
    """Extender acessivel, tipo refletido, mas NENHUMA interface de
    extensao reconhecida (ICustomTypeDescriptor/IDynamicMetaObjectProvider/
    IExtenderProvider ausentes) -- so membros CLR convencionais."""
    extender_type = FakeTypeRef(
        "Vendor.Extension.PlainObject",
        interfaces=[FakeInterfaceInfo("System.IDisposable")],
        properties=[FakePropertyInfo("SomeProp", "Vendor.Extension.PlainObject", "System.Int32")],
        methods=[])
    extender_obj = FakeExtenderObject(extender_type)
    clr_type = _clr_type_with_extender()
    target = _confirmed_target_node(clr_type, extender_value=extender_obj)
    application = _application_with_target(target)
    config = _base_ladder_probe_config()

    result = probe_mod.probe_ladder_extender_surface(application, config, str(tmp_path))

    assert result["extender_accessible"] is True
    assert result["extension_channel_enumerable"] is False
    assert result["control_provider_found"] is False
    assert result["result_case"] == "E3"
    assert result["status"] == "inconclusive"

    runtime_type = json.loads(
        (tmp_path / "extender-runtime-type.json").read_text(encoding="utf-8"))
    assert runtime_type["implements_icustomtypedescriptor"] is False


def test_case_E3_regra_contra_falso_sucesso_many_members_but_control_not_found(tmp_path):
    """A REGRA CENTRAL: Extender acessivel + muitos membros refletidos +
    controle NAO localizado -- SEMPRE E3, jamais sucesso. O provider expoe
    40 property descriptors, nenhum chamado 'textual_declaration'."""
    descriptors = [FakePropertyDescriptor("Prop%02d" % i) for i in range(40)]
    extender_type = _ctd_extender_type()
    extender_obj = FakeExtenderObject(extender_type, descriptors=descriptors)
    clr_type = _clr_type_with_extender()
    target = _confirmed_target_node(clr_type, extender_value=extender_obj)
    application = _application_with_target(target)
    config = _base_ladder_probe_config()

    result = probe_mod.probe_ladder_extender_surface(application, config, str(tmp_path))

    assert result["extender_accessible"] is True
    assert result["extension_channel_enumerable"] is True
    assert result["extension_item_count"] == 40
    assert result["control_provider_found"] is False
    assert result["extender_channel_validated"] is False
    assert result["result_case"] == "E3"
    assert result["status"] == "inconclusive"

    discovery = json.loads(
        (tmp_path / "known-control-discovery.json").read_text(encoding="utf-8"))
    assert discovery["control_provider_found"] is False
    assert discovery["extender_channel_validated"] is False
    assert "reason" in discovery


def test_case_E3_provider_not_enumerable_get_properties_raises(tmp_path):
    """ICustomTypeDescriptor confirmado, mas GetProperties() falha."""
    extender_type = _ctd_extender_type()
    extender_obj = FakeExtenderObject(extender_type, get_properties_raises=RuntimeError("falhou"))
    clr_type = _clr_type_with_extender()
    target = _confirmed_target_node(clr_type, extender_value=extender_obj)
    application = _application_with_target(target)
    config = _base_ladder_probe_config()

    result = probe_mod.probe_ladder_extender_surface(application, config, str(tmp_path))

    assert result["extender_accessible"] is True
    assert result["extension_channel_enumerable"] is False
    assert result["result_case"] == "E3"


def test_case_E3_provider_returns_collection_without_known_interface(tmp_path):
    """GetProperties() retorna algo, mas a colecao NAO implementa nenhuma
    interface de colecao conhecida -- enumeracao bloqueada (contrato item 4).
    """
    descriptors = [FakePropertyDescriptor("textual_declaration")]
    extender_type = _ctd_extender_type()
    extender_obj = FakeExtenderObject(
        extender_type, descriptors=descriptors, collection_implements_known_interface=False)
    clr_type = _clr_type_with_extender()
    target = _confirmed_target_node(clr_type, extender_value=extender_obj)
    application = _application_with_target(target)
    config = _base_ladder_probe_config()

    result = probe_mod.probe_ladder_extender_surface(application, config, str(tmp_path))

    assert result["extension_channel_enumerable"] is False
    assert result["control_provider_found"] is False
    assert result["result_case"] == "E3"


def test_case_E3_enumeration_occurs_but_control_absent(tmp_path):
    """Enumeracao REAL funciona (ICustomTypeDescriptor confirmado, colecao
    IList confirmada, itens lidos), mas nenhum item se chama
    'textual_declaration' -- canal enumeravel, controle nao reencontrado."""
    descriptors = [FakePropertyDescriptor("NetworkBuffer"), FakePropertyDescriptor("Other")]
    extender_type = _ctd_extender_type()
    extender_obj = FakeExtenderObject(extender_type, descriptors=descriptors)
    clr_type = _clr_type_with_extender()
    target = _confirmed_target_node(clr_type, extender_value=extender_obj)
    application = _application_with_target(target)
    config = _base_ladder_probe_config()

    result = probe_mod.probe_ladder_extender_surface(application, config, str(tmp_path))

    assert result["extension_channel_enumerable"] is True
    assert result["control_provider_found"] is False
    assert result["result_case"] == "E3"
    # mesmo com um candidato Ladder classificado, sem o controle o veredito
    # continua E3 -- candidate_count so importa DEPOIS do canal validado.
    assert result["ladder_candidate_count"] >= 1


# =============================================================================
# 3. E1/E2 -- canal validado (controle reencontrado).
# =============================================================================

def test_case_E1_validated_channel_zero_candidates(tmp_path):
    descriptors = [
        FakePropertyDescriptor("textual_declaration", property_type_name="System.String"),
        FakePropertyDescriptor("SomethingElse"),
    ]
    extender_type = _ctd_extender_type()
    extender_obj = FakeExtenderObject(extender_type, descriptors=descriptors)
    clr_type = _clr_type_with_extender()
    target = _confirmed_target_node(clr_type, extender_value=extender_obj)
    application = _application_with_target(target)
    config = _base_ladder_probe_config()

    result = probe_mod.probe_ladder_extender_surface(application, config, str(tmp_path))

    assert result["extender_channel_validated"] is True
    assert result["control_provider_found"] is True
    assert result["ladder_candidate_count"] == 0
    assert result["result_case"] == "E1"
    assert result["status"] == "ok"

    report = (tmp_path / "report.md").read_text(encoding="utf-8")
    assert "nenhum candidato no canal examinado" in report
    assert "NAO afirma ausencia global" in report

    discovery = json.loads(
        (tmp_path / "known-control-discovery.json").read_text(encoding="utf-8"))
    assert discovery["control_member"] == "textual_declaration"
    stages = [s["stage"] for s in discovery["discovery_path"]]
    assert stages == ["proxy", "extender", "provider", "property_descriptor"]
    last_stage = discovery["discovery_path"][-1]
    assert last_stage["name"] == "textual_declaration"
    assert last_stage["property_type"] == "System.String"


def test_case_E2_validated_channel_with_candidate(tmp_path):
    descriptors = [
        FakePropertyDescriptor("textual_declaration"),
        FakePropertyDescriptor("NetworkBuffer"),
    ]
    extender_type = _ctd_extender_type()
    extender_obj = FakeExtenderObject(extender_type, descriptors=descriptors)
    clr_type = _clr_type_with_extender()
    target = _confirmed_target_node(clr_type, extender_value=extender_obj)
    application = _application_with_target(target)
    config = _base_ladder_probe_config()

    result = probe_mod.probe_ladder_extender_surface(application, config, str(tmp_path))

    assert result["extender_channel_validated"] is True
    assert result["ladder_candidate_count"] == 1
    assert result["result_case"] == "E2"
    assert result["status"] == "ok"

    candidates = json.loads(
        (tmp_path / "ladder-candidate-members.json").read_text(encoding="utf-8"))
    assert len(candidates) == 1
    assert candidates[0]["name"] == "NetworkBuffer"
    assert candidates[0]["invoked"] is False
    assert candidates[0]["forbidden_term"] is None


def test_forbidden_term_candidate_marked_but_never_invoked(tmp_path):
    descriptors = [
        FakePropertyDescriptor("textual_declaration"),
        FakePropertyDescriptor("export_xml"),
    ]
    extender_type = _ctd_extender_type()
    extender_obj = FakeExtenderObject(extender_type, descriptors=descriptors)
    clr_type = _clr_type_with_extender()
    target = _confirmed_target_node(clr_type, extender_value=extender_obj)
    application = _application_with_target(target)
    config = _base_ladder_probe_config()

    result = probe_mod.probe_ladder_extender_surface(application, config, str(tmp_path))

    assert result["result_case"] == "E2"
    candidates = json.loads(
        (tmp_path / "ladder-candidate-members.json").read_text(encoding="utf-8"))
    entry = next(c for c in candidates if c["name"] == "export_xml")
    assert entry["forbidden_term"] == "export"
    assert "forbidden in this phase" in entry["reason_not_invoked"]
    assert entry["invoked"] is False


def test_duplicate_names_detected(tmp_path):
    descriptors = [
        FakePropertyDescriptor("textual_declaration"),
        FakePropertyDescriptor("NetworkBuffer"),
        FakePropertyDescriptor("NetworkBuffer"),
    ]
    extender_type = _ctd_extender_type()
    extender_obj = FakeExtenderObject(extender_type, descriptors=descriptors)
    clr_type = _clr_type_with_extender()
    target = _confirmed_target_node(clr_type, extender_value=extender_obj)
    application = _application_with_target(target)
    config = _base_ladder_probe_config()

    probe_mod.probe_ladder_extender_surface(application, config, str(tmp_path))

    items = json.loads((tmp_path / "extension-items.json").read_text(encoding="utf-8"))
    dup_flags = [i["duplicate"] for i in items if i["name"] == "NetworkBuffer"]
    assert dup_flags == [False, True]


def test_item_limit_respected(tmp_path):
    descriptors = ([FakePropertyDescriptor("textual_declaration")]
                  + [FakePropertyDescriptor("Prop%03d" % i) for i in range(300)])
    extender_type = _ctd_extender_type()
    extender_obj = FakeExtenderObject(extender_type, descriptors=descriptors)
    clr_type = _clr_type_with_extender()
    target = _confirmed_target_node(clr_type, extender_value=extender_obj)
    application = _application_with_target(target)
    config = _base_ladder_probe_config()

    result = probe_mod.probe_ladder_extender_surface(application, config, str(tmp_path))

    assert result["extension_item_count"] == probe_mod.MAX_EXTENSION_ITEMS
    items = json.loads((tmp_path / "extension-items.json").read_text(encoding="utf-8"))
    assert len(items) == probe_mod.MAX_EXTENSION_ITEMS


# =============================================================================
# 4. Proibicoes explicitas -- GetValue/SetValue/GetMetaObject/CanExtend
#    nunca chamados; '.text' nunca lido; proxy/Extender/PropertyDescriptor
#    nunca serializados via str()/repr()/ToString().
# =============================================================================

def test_never_calls_get_value_set_value_get_meta_object_can_extend(tmp_path):
    """Os fakes levantam AssertionError se qualquer um desses metodos for
    chamado -- chegar ate aqui sem excecao ja prova a proibicao. Cenario
    cobre tambem o caso em que GetMetaObject/CanExtend aparecem na reflexao
    de metodos (contrato item 6/7: presenca registrada, nunca invocada)."""
    descriptors = [FakePropertyDescriptor("textual_declaration"), FakePropertyDescriptor("NetworkBuffer")]
    extra_methods = [
        FakeMethodInfo("GetMetaObject", "Vendor.Extension.ExtenderObject",
                       "System.Dynamic.DynamicMetaObject",
                       parameters=[FakeParameterInfo("parameter", "System.Linq.Expressions.Expression")]),
        FakeMethodInfo("CanExtend", "Vendor.Extension.ExtenderObject", "System.Boolean",
                       parameters=[FakeParameterInfo("extendee", "System.Object")]),
    ]
    extender_type = _ctd_extender_type(
        extra_interfaces=[FakeInterfaceInfo("System.ComponentModel.IExtenderProvider"),
                         FakeInterfaceInfo("System.Dynamic.IDynamicMetaObjectProvider")],
        extra_methods=extra_methods)
    extender_obj = FakeExtenderObject(extender_type, descriptors=descriptors)
    clr_type = _clr_type_with_extender()
    target = _confirmed_target_node(clr_type, extender_value=extender_obj)
    application = _application_with_target(target)
    config = _base_ladder_probe_config()

    result = probe_mod.probe_ladder_extender_surface(application, config, str(tmp_path))

    assert result["result_case"] == "E2"
    runtime_type = json.loads(
        (tmp_path / "extender-runtime-type.json").read_text(encoding="utf-8"))
    assert runtime_type["implements_iextenderprovider"] is True
    assert runtime_type["implements_idynamicmetaobjectprovider"] is True
    assert runtime_type["has_get_meta_object_method"] is True
    assert runtime_type["has_can_extend_method"] is True


def test_dot_text_never_read_on_proxy(tmp_path):
    clr_type = _clr_type_with_extender()
    target = _confirmed_target_node(clr_type)
    application = _application_with_target(target)
    config = _base_ladder_probe_config()

    probe_mod.probe_ladder_extender_surface(application, config, str(tmp_path))

    assert target.text_accessed is False


def test_str_repr_never_called_on_proxy_or_extender_or_descriptor(tmp_path):
    """FakeNode/FakeExtenderObject/FakePropertyDescriptor levantam
    AssertionError em __str__/__repr__ -- chegar ate aqui sem excecao ja
    prova a proibicao (contrato: nenhuma serializacao de proxy)."""
    descriptors = [FakePropertyDescriptor("textual_declaration"), FakePropertyDescriptor("NetworkBuffer")]
    extender_type = _ctd_extender_type()
    extender_obj = FakeExtenderObject(extender_type, descriptors=descriptors)
    clr_type = _clr_type_with_extender()
    target = _confirmed_target_node(clr_type, extender_value=extender_obj)
    application = _application_with_target(target)
    config = _base_ladder_probe_config()

    result = probe_mod.probe_ladder_extender_surface(application, config, str(tmp_path))
    assert result["result_case"] == "E2"


# =============================================================================
# 5. Identidade divergente aborta ANTES de sondar o Extender.
# =============================================================================

def test_identity_mismatch_aborts_before_probing_extender(tmp_path):
    clr_type = _clr_type_with_extender()
    target = FakeNode(
        name="NOME_ERRADO", type_guid=TARGET_TYPE_GUID, object_guid=TARGET_GUID, is_folder=False,
        clr_type=clr_type, extra_properties={"Extender": RuntimeError("NUNCA deveria ser chamado")})
    application = _application_with_target(target)
    config = _base_ladder_probe_config()

    result = probe_mod.probe_ladder_extender_surface(application, config, str(tmp_path))

    assert result["aborted"] is True
    assert result["abort_reason"] == "target_identity_mismatch"
    assert result["target_identity_confirmed"] is False
    assert result["extender_accessible"] is False
    assert result["result_case"] == "E4"

    member = json.loads((tmp_path / "extender-member.json").read_text(encoding="utf-8"))
    assert member == {}
    items = json.loads((tmp_path / "extension-items.json").read_text(encoding="utf-8"))
    assert items == []


# =============================================================================
# 6. Colecao SEM interface conhecida NAO e enumerada -- teste dedicado
#    complementar (contrato item 4: "NUNCA iteracao livre sobre proxy
#    desconhecido").
# =============================================================================

class FakeUnknownIterableCollection(object):
    """Colecao que expoe Count + indexador mas cujo GetType() NAO reporta
    nenhuma interface de colecao conhecida -- o probe deve recusar a
    enumerar, mesmo que o acesso indexado 'funcionaria' na pratica."""

    def __init__(self, items):
        self._items = list(items)
        self._clr_type = FakeTypeRef(
            "Vendor.Extension.MysteryBag",
            interfaces=[FakeInterfaceInfo("System.Runtime.Serialization.ISerializable")])

    @property
    def Count(self):
        return len(self._items)

    def __getitem__(self, index):
        raise AssertionError("indexador NUNCA deveria ser acessado sem interface conhecida.")

    def GetType(self):
        return self._clr_type


def test_collection_without_known_interface_is_never_indexed(tmp_path):
    extender_type = _ctd_extender_type()

    class _ExtenderWithMysteryCollection(FakeExtenderObject):
        def GetProperties(self):
            return FakeUnknownIterableCollection(
                [FakePropertyDescriptor("textual_declaration")])

    extender_obj = _ExtenderWithMysteryCollection(extender_type)
    clr_type = _clr_type_with_extender()
    target = _confirmed_target_node(clr_type, extender_value=extender_obj)
    application = _application_with_target(target)
    config = _base_ladder_probe_config()

    result = probe_mod.probe_ladder_extender_surface(application, config, str(tmp_path))

    assert result["extension_channel_enumerable"] is False
    assert result["result_case"] == "E3"


# =============================================================================
# 7. classify_extender_probe_result -- funcao pura, testada em isolamento.
# =============================================================================

def test_classify_pure_function_all_cases():
    case, status, _ = probe_mod.classify_extender_probe_result(False, False, False, 0, 0)
    assert (case, status) == ("E4", "inconclusive")

    case, status, _ = probe_mod.classify_extender_probe_result(True, False, False, 0, 0)
    assert (case, status) == ("E3", "inconclusive")

    case, status, _ = probe_mod.classify_extender_probe_result(True, True, False, 0, 5)
    assert (case, status) == ("E3", "inconclusive")

    # regra contra falso sucesso: muitos itens, controle nao encontrado.
    case, status, _ = probe_mod.classify_extender_probe_result(True, True, False, 0, 40)
    assert (case, status) == ("E3", "inconclusive")

    case, status, _ = probe_mod.classify_extender_probe_result(True, True, True, 0, 3)
    assert (case, status) == ("E1", "ok")

    case, status, _ = probe_mod.classify_extender_probe_result(True, True, True, 2, 5)
    assert (case, status) == ("E2", "ok")


# =============================================================================
# 8. safety-declaration.json -- 10 chaves exatas, todas False.
# =============================================================================

def test_safety_declaration_has_exactly_10_keys_all_false(tmp_path):
    clr_type = _clr_type_with_extender()
    target = _confirmed_target_node(clr_type)
    application = _application_with_target(target)
    config = _base_ladder_probe_config()

    probe_mod.probe_ladder_extender_surface(application, config, str(tmp_path))

    declaration = json.loads((tmp_path / "safety-declaration.json").read_text(encoding="utf-8"))
    expected_keys = {
        "text_document_read", "text_document_write", "export_called", "import_called",
        "save_called", "build_called", "online_operation", "download_called",
        "force_called", "project_modified",
    }
    assert set(declaration.keys()) == expected_keys
    assert all(value is False for value in declaration.values())


def test_safety_declaration_written_even_when_aborted(tmp_path):
    target = FakeNode(name="ERRADO", type_guid="errado", object_guid="errado", is_folder=False)
    application = _application_with_target(target)
    config = _base_ladder_probe_config()

    result = probe_mod.probe_ladder_extender_surface(application, config, str(tmp_path))

    assert result["aborted"] is True
    declaration = json.loads((tmp_path / "safety-declaration.json").read_text(encoding="utf-8"))
    assert all(value is False for value in declaration.values())


# =============================================================================
# 9. Artefatos obrigatorios sempre presentes + checksums.sha256 por ultimo.
# =============================================================================

REQUIRED_ARTIFACTS = (
    "manifest.json", "target-identity.json", "extender-member.json",
    "extender-runtime-type.json", "extender-interfaces.json", "extender-properties.json",
    "extender-methods.json", "extension-items.json", "extension-item-types.json",
    "known-control-discovery.json", "ladder-candidate-members.json", "diagnostics.json",
    "safety-declaration.json", "checksums.sha256", "report.md",
)


def test_all_required_artifacts_exist_on_happy_path(tmp_path):
    descriptors = [FakePropertyDescriptor("textual_declaration")]
    extender_type = _ctd_extender_type()
    extender_obj = FakeExtenderObject(extender_type, descriptors=descriptors)
    clr_type = _clr_type_with_extender()
    target = _confirmed_target_node(clr_type, extender_value=extender_obj)
    application = _application_with_target(target)
    config = _base_ladder_probe_config()

    probe_mod.probe_ladder_extender_surface(application, config, str(tmp_path))

    for filename in REQUIRED_ARTIFACTS:
        assert (tmp_path / filename).is_file(), "artefato ausente: %s" % filename


def test_all_required_artifacts_exist_on_abort(tmp_path):
    target = FakeNode(name="ERRADO", type_guid="errado", object_guid="errado", is_folder=False)
    application = _application_with_target(target)
    config = _base_ladder_probe_config()

    probe_mod.probe_ladder_extender_surface(application, config, str(tmp_path))

    for filename in REQUIRED_ARTIFACTS:
        assert (tmp_path / filename).is_file(), "artefato ausente: %s" % filename


def test_checksums_cover_manifest_and_known_control_discovery(tmp_path):
    clr_type = _clr_type_with_extender()
    target = _confirmed_target_node(clr_type)
    application = _application_with_target(target)
    config = _base_ladder_probe_config()

    probe_mod.probe_ladder_extender_surface(application, config, str(tmp_path))

    checksums_text = (tmp_path / "checksums.sha256").read_text(encoding="utf-8")
    assert "manifest.json" in checksums_text
    assert "known-control-discovery.json" in checksums_text
    assert "safety-declaration.json" in checksums_text


# =============================================================================
# 10. Configuracao invalida do proprio ladder_probe_config (defesa em
#     profundidade, mesma regra dos probes 16/17).
# =============================================================================

def test_missing_required_config_field_aborts_without_navigating(tmp_path):
    application = _application_with_target(_confirmed_target_node(_clr_type_with_extender()))
    config = _base_ladder_probe_config()
    del config["expected_guid"]

    result = probe_mod.probe_ladder_extender_surface(application, config, str(tmp_path))

    assert result["aborted"] is True
    assert result["abort_reason"] == "ladder_probe_config_invalid"


def test_probe_never_raises_even_with_completely_malformed_config(tmp_path):
    application = _application_with_target(_confirmed_target_node(_clr_type_with_extender()))
    result = probe_mod.probe_ladder_extender_surface(application, "not-a-dict", str(tmp_path))
    assert result["aborted"] is True
    assert result["abort_reason"] == "ladder_probe_config_invalid"


def test_invalid_target_node_id_aborts(tmp_path):
    application = _application_with_target(_confirmed_target_node(_clr_type_with_extender()))
    config = _base_ladder_probe_config(target_node_id="not-application/0/1")

    result = probe_mod.probe_ladder_extender_surface(application, config, str(tmp_path))

    assert result["aborted"] is True
    assert result["abort_reason"] == "invalid_target_node_id"


def test_navigation_index_out_of_range_aborts(tmp_path):
    application = _application_with_target(_confirmed_target_node(_clr_type_with_extender()))
    config = _base_ladder_probe_config(target_node_id="application/0/999")

    result = probe_mod.probe_ladder_extender_surface(application, config, str(tmp_path))

    assert result["aborted"] is True
    assert result["abort_reason"] == "navigation_failed"


# =============================================================================
# Ramo Array -- lacuna de cobertura fechada.
#
# O contrato autoriza enumerar quando a colecao for `Array`, e o probe checa
# `IsArray` alem de GetInterfaces(). Sem este teste o ramo existia so na
# logica: um Array real (que NAO implementa IList entre as interfaces
# refletidas neste duble) nunca era exercitado.
# =============================================================================

class FakeArrayType(FakeTypeRef):
    """Tipo CLR de Array: IsArray=True e SEM interface de colecao conhecida
    entre as refletidas -- e exatamente o caso que so `IsArray` resolve."""

    def __init__(self):
        FakeTypeRef.__init__(
            self, "System.ComponentModel.PropertyDescriptor[]",
            interfaces=[FakeInterfaceInfo("System.Collections.IEnumerable")])
        self.IsArray = True


class FakeArrayCollection(object):
    def __init__(self, items):
        self._items = list(items)
        self._clr_type = FakeArrayType()

    @property
    def Count(self):
        return len(self._items)

    def __getitem__(self, index):
        return self._items[index]

    def GetType(self):
        return self._clr_type


class FakeArrayExtenderObject(FakeExtenderObject):
    def GetProperties(self):
        return FakeArrayCollection(self._descriptors)


def test_array_collection_is_enumerated_and_validates_the_channel(tmp_path):
    descriptors = [
        FakePropertyDescriptor("textual_declaration", "IScriptTextDocument"),
        FakePropertyDescriptor("NetworkBuffer", "System.Object"),
    ]
    extender = FakeArrayExtenderObject(
        clr_type=_ctd_extender_type(), descriptors=descriptors)
    target = _confirmed_target_node(
        clr_type=_clr_type_with_extender(), extender_value=extender)

    result = probe_mod.probe_ladder_extender_surface(
        _application_with_target(target), _base_ladder_probe_config(), str(tmp_path))

    # Array conta como colecao conhecida -> enumeracao acontece -> o controle
    # e reencontrado -> canal validado.
    assert result["extension_channel_enumerable"] is True
    assert result["control_provider_found"] is True
    assert result["extender_channel_validated"] is True
    assert result["result_case"] == "E2"

    items = json.loads((tmp_path / "extension-items.json").read_text(encoding="utf-8"))
    assert len(items) == 2

    diagnostics = json.loads((tmp_path / "diagnostics.json").read_text(encoding="utf-8"))
    assert any("IsArray" in d.get("message", "") for d in diagnostics), (
        "o diagnostico deve registrar que a colecao foi aceita por IsArray, "
        "nao por interface refletida")


def test_array_collection_without_control_still_refuses_to_validate(tmp_path):
    """O ramo Array nao pode virar atalho para validar o canal."""
    extender = FakeArrayExtenderObject(
        clr_type=_ctd_extender_type(),
        descriptors=[FakePropertyDescriptor("banana", "System.Object")])
    target = _confirmed_target_node(
        clr_type=_clr_type_with_extender(), extender_value=extender)

    result = probe_mod.probe_ladder_extender_surface(
        _application_with_target(target), _base_ladder_probe_config(), str(tmp_path))

    assert result["extension_channel_enumerable"] is True
    assert result["control_provider_found"] is False
    assert result["extender_channel_validated"] is False
    assert result["result_case"] == "E3"

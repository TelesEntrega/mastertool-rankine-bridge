"""Testa scripts/mastertool/probes/19_probe_plcopen_xml_export_signature.py
EM ISOLAMENTO (lado IronPython 2.7, roda DENTRO do MasterTool) -- Fase L1
(docs/14-ladder-roadmap.md), IRMAO de test_probe_18_ladder_extender_surface.py.

Mesma filosofia de dubles (fakes) que os testes dos probes 16/17/18: nenhum
proxy CLR real, so o suficiente para exercitar navegacao bounded/indexada +
identidade + reflexao de sobrecargas de export_xml/import_xml + escopo +
IExportReporter + enum ConflictResolve + classificacao S1/S2/S3.

Carregamento do modulo: o arquivo comeca com digito ('19_...'), entao
'import probes.19_probe...' e SyntaxError -- e preciso carregar pelo
CAMINHO, mesmo mecanismo usado por test_probe_18_ladder_extender_surface.py
(tentar importlib.util, cair para imp so em IronPython 2.7).
"""

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_MASTERTOOL = REPO_ROOT / "scripts" / "mastertool"
PROBE_PATH = SCRIPTS_MASTERTOOL / "probes" / "19_probe_plcopen_xml_export_signature.py"

if str(SCRIPTS_MASTERTOOL) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_MASTERTOOL))


def _load_probe_module():
    module_name = "mastertool_bridge_probe_19_plcopen_export_signature"
    try:
        import importlib.util as _importlib_util
    except ImportError:
        _importlib_util = None

    if _importlib_util is not None and hasattr(_importlib_util, "spec_from_file_location"):
        spec = _importlib_util.spec_from_file_location(module_name, str(PROBE_PATH))
        if spec is None or spec.loader is None:
            raise ImportError("nao foi possivel montar o spec do probe 19: %s" % PROBE_PATH)
        module = _importlib_util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module

    import imp  # IronPython 2.7: unico mecanismo disponivel
    return imp.load_source(module_name, str(PROBE_PATH))


probe_mod = _load_probe_module()


# =============================================================================
# Dubles (fakes) -- proxies/reflexao CLR minimos.
# =============================================================================

class FakeAssembly(object):
    def __init__(self, full_name):
        self.FullName = full_name


class FakeTypeRef(object):
    """Representa um System.Type -- para parametros, tipos de retorno, e o
    proprio GetType() de um objeto. So expoe metadados: nunca invocado como
    instancia real."""

    def __init__(self, full_name, assembly_full_name="TestAssembly, Version=1.0.0.0",
                methods=None, is_interface=False, is_enum=False, is_by_ref=False,
                members=None, enum_names=None, fields=None):
        self.FullName = full_name
        self.Assembly = FakeAssembly(assembly_full_name)
        self._methods = methods or []
        self.IsInterface = is_interface
        self.IsEnum = is_enum
        self.IsByRef = is_by_ref
        self._members = members if members is not None else []
        self._enum_names = enum_names
        self._fields = fields or []

    def GetMethods(self):
        return self._methods

    def GetMembers(self):
        return self._members

    def GetEnumNames(self):
        if self._enum_names is None:
            raise RuntimeError("GetEnumNames() indisponivel neste tipo (duble).")
        return self._enum_names

    def GetFields(self):
        return self._fields

    def __str__(self):
        raise AssertionError("str() NUNCA deveria ser chamado sobre um System.Type.")

    def __repr__(self):
        raise AssertionError("repr() NUNCA deveria ser chamado sobre um System.Type.")


class FakeFieldInfo(object):
    def __init__(self, name):
        self.Name = name


class FakeMemberInfo(object):
    def __init__(self, name, member_type_value=8):
        self.Name = name
        self.MemberType = member_type_value  # 8 == Method, no MemberTypes real


class FakeParameterInfo(object):
    def __init__(self, name, type_name, position=0, is_optional=False, has_default_value=False,
                default_value=None, raw_default_value=None, is_out=False, is_in=True,
                is_by_ref=False, type_assembly="TestAssembly, Version=1.0.0.0"):
        self.Name = name
        self.ParameterType = FakeTypeRef(type_name, assembly_full_name=type_assembly,
                                         is_by_ref=is_by_ref)
        self.Position = position
        self.IsOptional = is_optional
        self.HasDefaultValue = has_default_value
        self.DefaultValue = default_value
        self.RawDefaultValue = raw_default_value
        self.IsOut = is_out
        self.IsIn = is_in


class FakeMethodInfo(object):
    def __init__(self, name, declaring_type_name, return_type_name, parameters=None,
                is_static=False, is_public=True, attributes=None):
        self.Name = name
        self.DeclaringType = FakeTypeRef(declaring_type_name)
        self.ReturnType = FakeTypeRef(return_type_name)
        self.IsStatic = is_static
        self.IsPublic = is_public
        self._parameters = parameters or []
        self._attributes = attributes or []

    def GetParameters(self):
        return self._parameters

    def GetCustomAttributes(self, inherit):
        return self._attributes


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
    """Proxy CLR minimo do alvo (ou da Application)."""

    def __init__(self, name, type_guid, object_guid, is_folder, children=None, clr_type=None,
                get_type_raises=None):
        self._name = name
        self._type_guid = type_guid
        self._object_guid = object_guid
        self._is_folder = is_folder
        self._children = children or []
        self._clr_type = clr_type
        self._get_type_raises = get_type_raises
        self.text_accessed = False
        self.export_xml_called = False
        self.import_xml_called = False

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
        if self._get_type_raises is not None:
            raise self._get_type_raises
        if self._clr_type is None:
            raise AssertionError(
                "GetType() nao deveria ser chamado neste teste (clr_type nao configurado).")
        return self._clr_type

    def export_xml(self, *args, **kwargs):
        self.export_xml_called = True
        raise AssertionError("export_xml() NUNCA deveria ser chamado por este probe.")

    def import_xml(self, *args, **kwargs):
        self.import_xml_called = True
        raise AssertionError("import_xml() NUNCA deveria ser chamado por este probe.")

    def export_native(self, *args, **kwargs):
        raise AssertionError("export_native() NUNCA deveria ser chamado por este probe.")

    def import_native(self, *args, **kwargs):
        raise AssertionError("import_native() NUNCA deveria ser chamado por este probe.")

    @property
    def text(self):
        self.text_accessed = True
        return "NUNCA DEVERIA SER LIDO"

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


def _application_with_target(target_node, application_clr_type=None):
    """application/0/1 -> target_node (2 niveis, navegacao bounded)."""
    sibling = FakeNode(name="Outro", type_guid="x", object_guid="y", is_folder=False)
    intermediate = FakeNode(
        name="Pasta", type_guid="folder-type", object_guid="folder-guid", is_folder=True,
        children=[sibling, target_node])
    application = FakeNode(
        name="Application", type_guid="app-type", object_guid="app-guid", is_folder=False,
        children=[intermediate], clr_type=application_clr_type)
    return application


def _confirmed_target_node(clr_type):
    return FakeNode(
        name=TARGET_NAME, type_guid=TARGET_TYPE_GUID, object_guid=TARGET_GUID,
        is_folder=False, clr_type=clr_type)


REPORTER_TYPE_NAME = "Vendor.PlcOpenXml.IExportReporter"
CONFLICT_RESOLVE_TYPE_NAME = "_3S.CoDeSys.PLCopenXML.ConflictResolve"


def _reporter_param(name="reporter", position=0):
    return FakeParameterInfo(name, REPORTER_TYPE_NAME, position=position)


def _string_param(name="stPath", position=0):
    return FakeParameterInfo(name, "System.String", position=position)


def _bool_param(name="bRecursive", position=1):
    return FakeParameterInfo(name, "System.Boolean", position=position)


def _conflict_resolve_param(name="conflictResolve", position=1):
    return FakeParameterInfo(name, CONFLICT_RESOLVE_TYPE_NAME, position=position)


def _out_param(name="result", position=2):
    return FakeParameterInfo(name, "System.Boolean", position=position, is_out=True)


def _byref_param(name="ref", position=2):
    return FakeParameterInfo(name, "System.Boolean", position=position, is_by_ref=True)


def _export_xml_method(parameters, declaring_type="Vendor.ScriptEngine.IScriptObject"):
    return FakeMethodInfo("export_xml", declaring_type, "System.Void", parameters=parameters)


def _import_xml_method(parameters, declaring_type="Vendor.ScriptEngine.IScriptObject"):
    return FakeMethodInfo("import_xml", declaring_type, "System.Void", parameters=parameters)


def _clr_type_with_methods(methods):
    return FakeTypeRef("Vendor.ScriptEngine.ScriptObjectProxy", methods=methods)


# =============================================================================
# 1. S1 -- sobrecarga sem reporter, params primitivos.
# =============================================================================

def test_case_S1_overload_without_reporter_all_primitive_params(tmp_path):
    methods = [
        _export_xml_method([_string_param(), _bool_param(), _bool_param("bExportFolderStructure", 2),
                            _bool_param("bPlainText", 3)]),
        _export_xml_method([_string_param(), _reporter_param(position=1)]),
        _import_xml_method([_string_param(), _conflict_resolve_param()]),
    ]
    clr_type = _clr_type_with_methods(methods)
    target = _confirmed_target_node(clr_type)
    application = _application_with_target(target)
    config = _base_ladder_probe_config()

    result = probe_mod.probe_plcopen_export_signature(application, config, str(tmp_path))

    assert result["aborted"] is False
    assert result["export_xml_found"] is True
    assert result["export_xml_overload_count"] == 2
    assert result["result_case"] == "S1"
    assert result["status"] == "ok"

    overloads_doc = json.loads((tmp_path / "export-xml-overloads.json").read_text(encoding="utf-8"))
    assert overloads_doc["overload_count"] == 2
    assert overloads_doc["invoked"] is False
    assert overloads_doc["forbidden_term"] == "export"

    param_names = {p["name"] for ov in overloads_doc["overloads"] for p in ov["parameters"]}
    assert "bPlainText" in param_names


# =============================================================================
# 2. S2 -- so sobrecargas com IExportReporter.
# =============================================================================

def test_case_S2_only_reporter_overloads(tmp_path):
    methods = [
        _export_xml_method([_string_param(), _reporter_param(position=1)]),
        _export_xml_method([_string_param(), _bool_param(), _reporter_param(position=2)]),
    ]
    clr_type = _clr_type_with_methods(methods)
    target = _confirmed_target_node(clr_type)
    application = _application_with_target(target)
    config = _base_ladder_probe_config()

    result = probe_mod.probe_plcopen_export_signature(application, config, str(tmp_path))

    assert result["export_xml_found"] is True
    assert result["export_xml_overload_count"] == 2
    assert result["result_case"] == "S2"
    assert result["status"] == "inconclusive"


# =============================================================================
# 3. S2 -- parametro out/ref presente (mesmo sem reporter).
# =============================================================================

def test_case_S2_out_parameter_present(tmp_path):
    methods = [
        _export_xml_method([_string_param(), _bool_param(), _out_param()]),
    ]
    clr_type = _clr_type_with_methods(methods)
    target = _confirmed_target_node(clr_type)
    application = _application_with_target(target)
    config = _base_ladder_probe_config()

    result = probe_mod.probe_plcopen_export_signature(application, config, str(tmp_path))

    assert result["export_xml_found"] is True
    assert result["result_case"] == "S2"


def test_case_S2_byref_parameter_present(tmp_path):
    methods = [
        _export_xml_method([_string_param(), _bool_param(), _byref_param()]),
    ]
    clr_type = _clr_type_with_methods(methods)
    target = _confirmed_target_node(clr_type)
    application = _application_with_target(target)
    config = _base_ladder_probe_config()

    result = probe_mod.probe_plcopen_export_signature(application, config, str(tmp_path))

    assert result["export_xml_found"] is True
    assert result["result_case"] == "S2"


# =============================================================================
# 4. S3 -- metodo ausente.
# =============================================================================

def test_case_S3_method_absent(tmp_path):
    clr_type = _clr_type_with_methods([])
    target = _confirmed_target_node(clr_type)
    application = _application_with_target(target)
    config = _base_ladder_probe_config()

    result = probe_mod.probe_plcopen_export_signature(application, config, str(tmp_path))

    assert result["export_xml_found"] is False
    assert result["export_xml_overload_count"] == 0
    assert result["result_case"] == "S3"
    assert result["status"] == "inconclusive"

    overloads_doc = json.loads((tmp_path / "export-xml-overloads.json").read_text(encoding="utf-8"))
    assert overloads_doc["overload_count"] == 0


# =============================================================================
# 5. REGRA CONTRA FALSO SUCESSO -- 4 sobrecargas refletidas, nenhuma
#    invocavel -> S2, jamais S1.
# =============================================================================

def test_regra_contra_falso_sucesso_four_overloads_none_invocable(tmp_path):
    methods = [
        _export_xml_method([_string_param(), _reporter_param(position=1)]),
        _export_xml_method([_string_param(), _bool_param(), _reporter_param(position=2)]),
        _export_xml_method([_string_param(), _bool_param(), _bool_param("c", 2), _reporter_param(3)]),
        _export_xml_method([_reporter_param(0)]),
    ]
    clr_type = _clr_type_with_methods(methods)
    target = _confirmed_target_node(clr_type)
    application = _application_with_target(target)
    config = _base_ladder_probe_config()

    result = probe_mod.probe_plcopen_export_signature(application, config, str(tmp_path))

    assert result["export_xml_overload_count"] == 4
    assert result["result_case"] == "S2"
    assert result["status"] == "inconclusive"
    assert result["result_case"] != "S1"


# =============================================================================
# 6. export_xml/import_xml/export_native/import_native NUNCA invocados.
# =============================================================================

def test_export_xml_and_import_xml_never_invoked(tmp_path):
    methods = [
        _export_xml_method([_string_param(), _bool_param()]),
        _import_xml_method([_string_param(), _conflict_resolve_param()]),
    ]
    clr_type = _clr_type_with_methods(methods)
    target = _confirmed_target_node(clr_type)
    application = _application_with_target(target)
    config = _base_ladder_probe_config()

    result = probe_mod.probe_plcopen_export_signature(application, config, str(tmp_path))

    assert result["result_case"] == "S1"
    assert target.export_xml_called is False
    assert target.import_xml_called is False


# =============================================================================
# 7. proxy nunca serializado (__str__/__repr__/ToString) -- chegar ao fim sem
#    excecao ja prova a proibicao (fakes levantam AssertionError).
# =============================================================================

def test_proxy_never_stringified(tmp_path):
    methods = [_export_xml_method([_string_param(), _bool_param()])]
    clr_type = _clr_type_with_methods(methods)
    target = _confirmed_target_node(clr_type)
    application = _application_with_target(target)
    config = _base_ladder_probe_config()

    result = probe_mod.probe_plcopen_export_signature(application, config, str(tmp_path))
    assert result["result_case"] == "S1"


def test_dot_text_never_read(tmp_path):
    methods = [_export_xml_method([_string_param(), _bool_param()])]
    clr_type = _clr_type_with_methods(methods)
    target = _confirmed_target_node(clr_type)
    application = _application_with_target(target)
    config = _base_ladder_probe_config()

    probe_mod.probe_plcopen_export_signature(application, config, str(tmp_path))
    assert target.text_accessed is False


# =============================================================================
# 8. Optionality/defaults capturados quando existem, ausencia tratada sem
#    quebrar.
# =============================================================================

def test_optionality_and_defaults_captured(tmp_path):
    optional_param = FakeParameterInfo(
        "bPlainText", "System.Boolean", position=3, is_optional=True, has_default_value=True,
        default_value=False, raw_default_value=False)
    methods = [
        _export_xml_method([_string_param(), _bool_param(), _bool_param("bExportFolderStructure", 2),
                            optional_param]),
    ]
    clr_type = _clr_type_with_methods(methods)
    target = _confirmed_target_node(clr_type)
    application = _application_with_target(target)
    config = _base_ladder_probe_config()

    probe_mod.probe_plcopen_export_signature(application, config, str(tmp_path))

    overloads_doc = json.loads((tmp_path / "export-xml-overloads.json").read_text(encoding="utf-8"))
    param = next(p for p in overloads_doc["overloads"][0]["parameters"] if p["name"] == "bPlainText")
    assert param["is_optional"] is True
    assert param["has_default_value"] is True
    assert param["default_value"] is False


class _RaisingParameterInfo(object):
    """ParameterInfo cujas propriedades de optionality/default levantam --
    o probe deve tratar cada leitura isoladamente, sem quebrar o restante."""

    def __init__(self):
        self.Name = "opaque"
        self.ParameterType = FakeTypeRef("System.String")
        self.Position = 0

    @property
    def IsOptional(self):
        raise RuntimeError("IsOptional indisponivel neste runtime (duble).")

    @property
    def HasDefaultValue(self):
        raise RuntimeError("HasDefaultValue indisponivel neste runtime (duble).")

    @property
    def DefaultValue(self):
        raise RuntimeError("DefaultValue indisponivel neste runtime (duble).")

    @property
    def RawDefaultValue(self):
        raise RuntimeError("RawDefaultValue indisponivel neste runtime (duble).")

    @property
    def IsOut(self):
        raise RuntimeError("IsOut indisponivel neste runtime (duble).")

    @property
    def IsIn(self):
        raise RuntimeError("IsIn indisponivel neste runtime (duble).")


def test_missing_parameter_properties_do_not_crash(tmp_path):
    methods = [_export_xml_method([_RaisingParameterInfo()])]
    clr_type = _clr_type_with_methods(methods)
    target = _confirmed_target_node(clr_type)
    application = _application_with_target(target)
    config = _base_ladder_probe_config()

    result = probe_mod.probe_plcopen_export_signature(application, config, str(tmp_path))

    assert result["aborted"] is False
    overloads_doc = json.loads((tmp_path / "export-xml-overloads.json").read_text(encoding="utf-8"))
    param = overloads_doc["overloads"][0]["parameters"][0]
    assert param["name"] == "opaque"
    assert param["is_optional"] is None
    assert param["has_default_value"] is None
    assert param["is_out"] is None


# =============================================================================
# 9. Escopo -- metodo presente no POU e na Application -> registrado nos
#    dois niveis.
# =============================================================================

def test_export_scope_registered_at_pou_and_application(tmp_path):
    pou_methods = [_export_xml_method([_string_param(), _bool_param()],
                                       declaring_type="Vendor.ScriptEngine.IScriptObject")]
    app_methods = [_export_xml_method([_string_param()], declaring_type="Vendor.ScriptEngine.IScriptApplication")]
    pou_clr_type = _clr_type_with_methods(pou_methods)
    app_clr_type = _clr_type_with_methods(app_methods)
    target = _confirmed_target_node(pou_clr_type)
    application = _application_with_target(target, application_clr_type=app_clr_type)
    config = _base_ladder_probe_config()

    probe_mod.probe_plcopen_export_signature(application, config, str(tmp_path))

    scope = json.loads((tmp_path / "export-scope.json").read_text(encoding="utf-8"))
    by_level = {entry["level"]: entry for entry in scope}
    assert by_level["pou"]["found"] is True
    assert by_level["pou"]["declaring_types"] == ["Vendor.ScriptEngine.IScriptObject"]
    assert by_level["application"]["found"] is True
    assert by_level["application"]["declaring_types"] == ["Vendor.ScriptEngine.IScriptApplication"]
    assert by_level["project"]["attempted"] is False
    assert by_level["project"]["found"] is None


def test_export_scope_application_get_type_failure_registered_not_aborted(tmp_path):
    pou_methods = [_export_xml_method([_string_param(), _bool_param()])]
    pou_clr_type = _clr_type_with_methods(pou_methods)
    target = _confirmed_target_node(pou_clr_type)

    sibling = FakeNode(name="Outro", type_guid="x", object_guid="y", is_folder=False)
    intermediate = FakeNode(
        name="Pasta", type_guid="folder-type", object_guid="folder-guid", is_folder=True,
        children=[sibling, target])
    application = FakeNode(
        name="Application", type_guid="app-type", object_guid="app-guid", is_folder=False,
        children=[intermediate], get_type_raises=RuntimeError("GetType() indisponivel"))
    config = _base_ladder_probe_config()

    result = probe_mod.probe_plcopen_export_signature(application, config, str(tmp_path))

    assert result["aborted"] is False
    scope = json.loads((tmp_path / "export-scope.json").read_text(encoding="utf-8"))
    by_level = {entry["level"]: entry for entry in scope}
    assert by_level["application"]["found"] is False
    assert by_level["application"]["attempted"] is True
    assert "GetType()" in by_level["application"]["reason"]


# =============================================================================
# 10. Enum ConflictResolve enumerado sem invocacao.
# =============================================================================

def test_conflict_resolve_enum_enumerated_via_get_enum_names(tmp_path):
    conflict_type = FakeTypeRef(
        CONFLICT_RESOLVE_TYPE_NAME, is_enum=True, enum_names=["KeepOriginal", "Overwrite", "Rename"])
    param = FakeParameterInfo("conflictResolve", CONFLICT_RESOLVE_TYPE_NAME, position=1)
    param.ParameterType = conflict_type
    methods = [
        _export_xml_method([_string_param(), _bool_param()]),
        _import_xml_method([_string_param(), param]),
    ]
    clr_type = _clr_type_with_methods(methods)
    target = _confirmed_target_node(clr_type)
    application = _application_with_target(target)
    config = _base_ladder_probe_config()

    probe_mod.probe_plcopen_export_signature(application, config, str(tmp_path))

    enum_doc = json.loads((tmp_path / "conflict-resolve-enum.json").read_text(encoding="utf-8"))
    assert enum_doc["found"] is True
    assert enum_doc["full_name"] == CONFLICT_RESOLVE_TYPE_NAME
    assert enum_doc["is_enum"] is True
    assert enum_doc["members"] == ["KeepOriginal", "Overwrite", "Rename"]


def test_conflict_resolve_enum_falls_back_to_get_fields(tmp_path):
    conflict_type = FakeTypeRef(
        CONFLICT_RESOLVE_TYPE_NAME, is_enum=True, enum_names=None,
        fields=[FakeFieldInfo("value__"), FakeFieldInfo("KeepOriginal"), FakeFieldInfo("Overwrite")])
    param = FakeParameterInfo("conflictResolve", CONFLICT_RESOLVE_TYPE_NAME, position=1)
    param.ParameterType = conflict_type
    methods = [
        _export_xml_method([_string_param(), _bool_param()]),
        _import_xml_method([_string_param(), param]),
    ]
    clr_type = _clr_type_with_methods(methods)
    target = _confirmed_target_node(clr_type)
    application = _application_with_target(target)
    config = _base_ladder_probe_config()

    probe_mod.probe_plcopen_export_signature(application, config, str(tmp_path))

    enum_doc = json.loads((tmp_path / "conflict-resolve-enum.json").read_text(encoding="utf-8"))
    assert enum_doc["found"] is True
    assert "KeepOriginal" in enum_doc["members"]


def test_conflict_resolve_absent_when_import_xml_has_no_such_parameter(tmp_path):
    methods = [
        _export_xml_method([_string_param(), _bool_param()]),
        _import_xml_method([_string_param(), _bool_param("bOverwrite", 1)]),
    ]
    clr_type = _clr_type_with_methods(methods)
    target = _confirmed_target_node(clr_type)
    application = _application_with_target(target)
    config = _base_ladder_probe_config()

    probe_mod.probe_plcopen_export_signature(application, config, str(tmp_path))

    enum_doc = json.loads((tmp_path / "conflict-resolve-enum.json").read_text(encoding="utf-8"))
    assert enum_doc["found"] is False
    assert enum_doc["full_name"] is None
    assert enum_doc["members"] == []


# =============================================================================
# 11. IExportReporter caracterizado por reflexao, nunca instanciado.
# =============================================================================

def test_export_reporter_type_reflected(tmp_path):
    reporter_type = FakeTypeRef(
        REPORTER_TYPE_NAME, is_interface=True,
        members=[FakeMemberInfo("ReportError"), FakeMemberInfo("ReportWarning")])
    reporter_param = FakeParameterInfo("reporter", REPORTER_TYPE_NAME, position=1)
    reporter_param.ParameterType = reporter_type
    methods = [
        _export_xml_method([_string_param(), _bool_param()]),
        _export_xml_method([_string_param(), reporter_param]),
    ]
    clr_type = _clr_type_with_methods(methods)
    target = _confirmed_target_node(clr_type)
    application = _application_with_target(target)
    config = _base_ladder_probe_config()

    result = probe_mod.probe_plcopen_export_signature(application, config, str(tmp_path))

    reporter_doc = json.loads((tmp_path / "export-reporter-type.json").read_text(encoding="utf-8"))
    assert reporter_doc["found"] is True
    assert reporter_doc["full_name"] == REPORTER_TYPE_NAME
    assert reporter_doc["is_interface"] is True
    assert len(reporter_doc["members"]) == 2
    assert reporter_doc["has_overload_without_reporter"] is True
    # a sobrecarga sem reporter e primitiva -> S1, mesmo com IExportReporter presente.
    assert result["result_case"] == "S1"


def test_export_reporter_absent_when_no_such_parameter(tmp_path):
    methods = [_export_xml_method([_string_param(), _bool_param()])]
    clr_type = _clr_type_with_methods(methods)
    target = _confirmed_target_node(clr_type)
    application = _application_with_target(target)
    config = _base_ladder_probe_config()

    probe_mod.probe_plcopen_export_signature(application, config, str(tmp_path))

    reporter_doc = json.loads((tmp_path / "export-reporter-type.json").read_text(encoding="utf-8"))
    assert reporter_doc["found"] is False
    assert reporter_doc["full_name"] is None
    assert reporter_doc["members"] == []


# =============================================================================
# 12. Identidade divergente aborta ANTES de refletir.
# =============================================================================

def test_identity_mismatch_aborts_before_reflecting(tmp_path):
    clr_type = _clr_type_with_methods([_export_xml_method([_string_param()])])
    target = FakeNode(
        name="NOME_ERRADO", type_guid=TARGET_TYPE_GUID, object_guid=TARGET_GUID, is_folder=False,
        clr_type=clr_type)
    application = _application_with_target(target)
    config = _base_ladder_probe_config()

    result = probe_mod.probe_plcopen_export_signature(application, config, str(tmp_path))

    assert result["aborted"] is True
    assert result["abort_reason"] == "target_identity_mismatch"
    assert result["target_identity_confirmed"] is False
    assert result["export_xml_found"] is False
    assert result["result_case"] == "S3"

    overloads_doc = json.loads((tmp_path / "export-xml-overloads.json").read_text(encoding="utf-8"))
    assert overloads_doc["overloads"] == []
    assert target.export_xml_called is False


# =============================================================================
# 13. safety-declaration.json -- 10 chaves exatas, todas False.
# =============================================================================

def test_safety_declaration_has_exactly_10_keys_all_false(tmp_path):
    methods = [_export_xml_method([_string_param(), _bool_param()])]
    clr_type = _clr_type_with_methods(methods)
    target = _confirmed_target_node(clr_type)
    application = _application_with_target(target)
    config = _base_ladder_probe_config()

    probe_mod.probe_plcopen_export_signature(application, config, str(tmp_path))

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

    result = probe_mod.probe_plcopen_export_signature(application, config, str(tmp_path))

    assert result["aborted"] is True
    declaration = json.loads((tmp_path / "safety-declaration.json").read_text(encoding="utf-8"))
    assert all(value is False for value in declaration.values())


# =============================================================================
# 14. Artefatos obrigatorios sempre presentes + checksums.sha256 por ultimo.
# =============================================================================

REQUIRED_ARTIFACTS = (
    "manifest.json", "target-identity.json", "export-xml-overloads.json",
    "import-xml-overloads.json", "export-scope.json", "export-reporter-type.json",
    "conflict-resolve-enum.json", "diagnostics.json", "safety-declaration.json",
    "checksums.sha256", "report.md",
)


def test_all_required_artifacts_exist_on_happy_path(tmp_path):
    methods = [
        _export_xml_method([_string_param(), _bool_param()]),
        _import_xml_method([_string_param(), _conflict_resolve_param()]),
    ]
    clr_type = _clr_type_with_methods(methods)
    target = _confirmed_target_node(clr_type)
    application = _application_with_target(target)
    config = _base_ladder_probe_config()

    probe_mod.probe_plcopen_export_signature(application, config, str(tmp_path))

    for filename in REQUIRED_ARTIFACTS:
        assert (tmp_path / filename).is_file(), "artefato ausente: %s" % filename


def test_all_required_artifacts_exist_on_abort(tmp_path):
    target = FakeNode(name="ERRADO", type_guid="errado", object_guid="errado", is_folder=False)
    application = _application_with_target(target)
    config = _base_ladder_probe_config()

    probe_mod.probe_plcopen_export_signature(application, config, str(tmp_path))

    for filename in REQUIRED_ARTIFACTS:
        assert (tmp_path / filename).is_file(), "artefato ausente: %s" % filename


def test_checksums_cover_manifest_and_export_scope(tmp_path):
    methods = [_export_xml_method([_string_param(), _bool_param()])]
    clr_type = _clr_type_with_methods(methods)
    target = _confirmed_target_node(clr_type)
    application = _application_with_target(target)
    config = _base_ladder_probe_config()

    probe_mod.probe_plcopen_export_signature(application, config, str(tmp_path))

    checksums_text = (tmp_path / "checksums.sha256").read_text(encoding="utf-8")
    assert "manifest.json" in checksums_text
    assert "export-scope.json" in checksums_text
    assert "safety-declaration.json" in checksums_text


# =============================================================================
# 15. classify_signature_probe_result -- funcao pura, testada em isolamento.
# =============================================================================

def test_classify_pure_function_all_cases():
    case, status, _ = probe_mod.classify_signature_probe_result(False, [])
    assert (case, status) == ("S3", "inconclusive")

    reporter_only = [{"parameters": [
        {"name": "stPath", "type": "System.String", "is_out": False, "is_by_ref": False},
        {"name": "reporter", "type": REPORTER_TYPE_NAME, "is_out": False, "is_by_ref": False},
    ]}]
    case, status, _ = probe_mod.classify_signature_probe_result(True, reporter_only)
    assert (case, status) == ("S2", "inconclusive")

    out_param_overload = [{"parameters": [
        {"name": "stPath", "type": "System.String", "is_out": False, "is_by_ref": False},
        {"name": "result", "type": "System.Boolean", "is_out": True, "is_by_ref": False},
    ]}]
    case, status, _ = probe_mod.classify_signature_probe_result(True, out_param_overload)
    assert (case, status) == ("S2", "inconclusive")

    primitive_overload = [{"parameters": [
        {"name": "stPath", "type": "System.String", "is_out": False, "is_by_ref": False},
        {"name": "bRecursive", "type": "System.Boolean", "is_out": False, "is_by_ref": False},
    ]}]
    case, status, _ = probe_mod.classify_signature_probe_result(True, primitive_overload)
    assert (case, status) == ("S1", "ok")

    mixed = reporter_only + primitive_overload
    case, status, _ = probe_mod.classify_signature_probe_result(True, mixed)
    assert (case, status) == ("S1", "ok")


# =============================================================================
# 16. Configuracao invalida do proprio ladder_probe_config (defesa em
#     profundidade, mesma regra dos probes 16/17/18).
# =============================================================================

def test_missing_required_config_field_aborts_without_navigating(tmp_path):
    application = _application_with_target(
        _confirmed_target_node(_clr_type_with_methods([_export_xml_method([_string_param()])])))
    config = _base_ladder_probe_config()
    del config["expected_guid"]

    result = probe_mod.probe_plcopen_export_signature(application, config, str(tmp_path))

    assert result["aborted"] is True
    assert result["abort_reason"] == "ladder_probe_config_invalid"


def test_probe_never_raises_even_with_completely_malformed_config(tmp_path):
    application = _application_with_target(
        _confirmed_target_node(_clr_type_with_methods([_export_xml_method([_string_param()])])))
    result = probe_mod.probe_plcopen_export_signature(application, "not-a-dict", str(tmp_path))
    assert result["aborted"] is True
    assert result["abort_reason"] == "ladder_probe_config_invalid"


def test_invalid_target_node_id_aborts(tmp_path):
    application = _application_with_target(
        _confirmed_target_node(_clr_type_with_methods([_export_xml_method([_string_param()])])))
    config = _base_ladder_probe_config(target_node_id="not-application/0/1")

    result = probe_mod.probe_plcopen_export_signature(application, config, str(tmp_path))

    assert result["aborted"] is True
    assert result["abort_reason"] == "invalid_target_node_id"


def test_navigation_index_out_of_range_aborts(tmp_path):
    application = _application_with_target(
        _confirmed_target_node(_clr_type_with_methods([_export_xml_method([_string_param()])])))
    config = _base_ladder_probe_config(target_node_id="application/0/999")

    result = probe_mod.probe_plcopen_export_signature(application, config, str(tmp_path))

    assert result["aborted"] is True
    assert result["abort_reason"] == "navigation_failed"


# =============================================================================
# Escopo Application: separado do POU, e pulavel de forma HONESTA.
#
# "Nao procurei" e "nao existe" sao coisas diferentes. Confundi-las e o erro
# que ja custou duas reclassificacoes nesta trilha (caso B -> D no probe 17).
# =============================================================================

def _target_and_app_with_export(pou_params, app_params):
    def prm(n, t):
        return FakeParameterInfo(n, t)

    pou_methods = [FakeMethodInfo("export_xml", "V.Pou", "System.String",
                                  parameters=[prm(*p) for p in pou_params])]
    app_methods = [FakeMethodInfo("export_xml", "V.App", "System.String",
                                  parameters=[prm(*p) for p in app_params])] if app_params else []
    target = _confirmed_target_node(FakeTypeRef("V.Pou", methods=pou_methods))
    return _application_with_target(
        target, application_clr_type=FakeTypeRef("V.App", methods=app_methods))


_SAFE = [("stPath", "System.String"), ("bRecursive", "System.Boolean")]
_UNSAFE = [("reporter", "_3S.CoDeSys.ScriptEngine.BasicFunctionality.IExportReporter"),
           ("stPath", "System.String")]


def test_application_scope_is_recorded_separately_from_pou(tmp_path):
    app = _target_and_app_with_export(_SAFE, _SAFE)
    result = probe_mod.probe_plcopen_export_signature(
        app, _base_ladder_probe_config(), str(tmp_path))

    pou = json.loads((tmp_path / "export-xml-overloads.json").read_text(encoding="utf-8"))
    application = json.loads(
        (tmp_path / "active-application-overloads.json").read_text(encoding="utf-8"))

    assert pou["overloads"][0]["declaring_type"] == "V.Pou"
    assert application["overloads"][0]["declaring_type"] == "V.App"
    assert application["inspected"] is True
    assert result["target_object_result_case"] == "S1"
    assert result["active_application_result_case"] == "S1"


def test_s1_in_one_scope_does_not_promote_the_other(tmp_path):
    """POU invocavel, Application nao -- cada escopo classificado por si."""
    app = _target_and_app_with_export(_SAFE, _UNSAFE)
    result = probe_mod.probe_plcopen_export_signature(
        app, _base_ladder_probe_config(), str(tmp_path))

    assert result["target_object_result_case"] == "S1"
    assert result["active_application_result_case"] == "S2"


def test_s1_in_application_does_not_promote_the_pou(tmp_path):
    app = _target_and_app_with_export(_UNSAFE, _SAFE)
    result = probe_mod.probe_plcopen_export_signature(
        app, _base_ladder_probe_config(), str(tmp_path))

    assert result["target_object_result_case"] == "S2"
    assert result["active_application_result_case"] == "S1"


def test_skipping_application_records_not_attempted_never_not_found(tmp_path):
    app = _target_and_app_with_export(_SAFE, _SAFE)
    result = probe_mod.probe_plcopen_export_signature(
        app, _base_ladder_probe_config(), str(tmp_path),
        inspect_active_application=False)

    scope = json.loads((tmp_path / "export-scope.json").read_text(encoding="utf-8"))
    application_level = [lv for lv in scope if lv["level"] == "application"][0]

    assert application_level["attempted"] is False
    assert application_level["found"] is None, (
        "found=False significaria 'procurei e nao achei' -- aqui nao se procurou")
    assert "NAO significa ausencia" in application_level["reason"]
    assert result["active_application_result_case"] is None

    application = json.loads(
        (tmp_path / "active-application-overloads.json").read_text(encoding="utf-8"))
    assert application["inspected"] is False
    assert application["overload_count"] == 0


def test_application_scope_failure_is_structured_not_an_exception(tmp_path):
    class _ExplodingApp(FakeNode):
        def GetType(self):
            raise RuntimeError("Application indisponivel")

    target = _confirmed_target_node(FakeTypeRef("V.Pou", methods=[
        FakeMethodInfo("export_xml", "V.Pou", "System.String",
                       parameters=[FakeParameterInfo("stPath", "System.String")])]))
    sibling = FakeNode(name="Outro", type_guid="x", object_guid="y", is_folder=False)
    intermediate = FakeNode(name="Pasta", type_guid="f", object_guid="fg", is_folder=True,
                            children=[sibling, target])
    app = _ExplodingApp(name="Application", type_guid="a", object_guid="ag",
                        is_folder=False, children=[intermediate])

    result = probe_mod.probe_plcopen_export_signature(
        app, _base_ladder_probe_config(), str(tmp_path))

    assert result.get("aborted") is not True
    scope = json.loads((tmp_path / "export-scope.json").read_text(encoding="utf-8"))
    application_level = [lv for lv in scope if lv["level"] == "application"][0]
    assert application_level["attempted"] is True
    assert application_level["found"] is False
    assert "falhou" in application_level["reason"]

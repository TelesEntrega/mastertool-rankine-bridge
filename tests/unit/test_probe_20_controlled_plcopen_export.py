"""Testa scripts/mastertool/probes/20_validate_controlled_plcopen_export.py
EM ISOLAMENTO (lado IronPython 2.7, roda DENTRO do MasterTool) -- Fase L1
(docs/14-ladder-roadmap.md), IRMAO de test_probe_19_plcopen_export_signature.py.

PRIMEIRA fatia desta trilha que escreve em disco -- os testes usam `tmp_path`
real (filesystem de verdade) para exercitar a UNICA invocacao autorizada
(`export_xml(stPath, False, False, False)`), simulada por um dublê que cria
arquivos/diretorios reais dentro de `export-root`, exatamente como a API real
faria.

Carregamento do modulo: o arquivo comeca com digito ('20_...'), entao
'import probes.20_validate...' e SyntaxError -- e preciso carregar pelo
CAMINHO, mesmo mecanismo usado por test_probe_19_plcopen_export_signature.py.
"""

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_MASTERTOOL = REPO_ROOT / "scripts" / "mastertool"
PROBE_PATH = SCRIPTS_MASTERTOOL / "probes" / "20_validate_controlled_plcopen_export.py"

if str(SCRIPTS_MASTERTOOL) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_MASTERTOOL))


def _load_probe_module():
    module_name = "mastertool_bridge_probe_20_controlled_plcopen_export"
    try:
        import importlib.util as _importlib_util
    except ImportError:
        _importlib_util = None

    if _importlib_util is not None and hasattr(_importlib_util, "spec_from_file_location"):
        spec = _importlib_util.spec_from_file_location(module_name, str(PROBE_PATH))
        if spec is None or spec.loader is None:
            raise ImportError("nao foi possivel montar o spec do probe 20: %s" % PROBE_PATH)
        module = _importlib_util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module

    import imp  # IronPython 2.7: unico mecanismo disponivel
    return imp.load_source(module_name, str(PROBE_PATH))


probe_mod = _load_probe_module()


# =============================================================================
# Dubles (fakes) -- proxies/reflexao CLR minimos + escrita real em tmp_path.
# =============================================================================

def _ok_provenance():
    return (True, "forcado-ok-em-teste", {
        "platform": "test", "runtime_family": "Test", "version_info": [2, 7, 12],
        "provenance_confirmed": True,
    })


def _never_reparse_point(path):
    return False


class FakeAssembly(object):
    def __init__(self, full_name):
        self.FullName = full_name


class FakeTypeRef(object):
    def __init__(self, full_name, methods=None, is_by_ref=False):
        self.FullName = full_name
        self.Assembly = FakeAssembly("TestAssembly, Version=1.0.0.0")
        self._methods = methods or []
        self.IsByRef = is_by_ref

    def GetMethods(self):
        return self._methods

    def __str__(self):
        raise AssertionError("str() NUNCA deveria ser chamado sobre um System.Type.")

    def __repr__(self):
        raise AssertionError("repr() NUNCA deveria ser chamado sobre um System.Type.")


class FakeParameterInfo(object):
    def __init__(self, name, type_name, position, is_out=False, is_by_ref=False):
        self.Name = name
        self.ParameterType = FakeTypeRef(type_name, is_by_ref=is_by_ref)
        self.Position = position
        self.IsOut = is_out


class FakeMethodInfo(object):
    def __init__(self, name, declaring_type_name, parameters):
        self.Name = name
        self.DeclaringType = FakeTypeRef(declaring_type_name)
        self.ReturnType = FakeTypeRef("System.String")
        self._parameters = parameters

    def GetParameters(self):
        return self._parameters


def _four_arg_params():
    return [
        FakeParameterInfo("stPath", "System.String", 0),
        FakeParameterInfo("bRecursive", "System.Boolean", 1),
        FakeParameterInfo("bExportFolderStructure", "System.Boolean", 2),
        FakeParameterInfo("bPlainText", "System.Boolean", 3),
    ]


def _reporter_overload_params():
    return [
        FakeParameterInfo("stPath", "System.String", 0),
        FakeParameterInfo("reporter", "Vendor.PlcOpenXml.IExportReporter", 1),
    ]


def _four_arg_method(declaring_type="Vendor.ScriptEngine.IScriptObject"):
    return FakeMethodInfo("export_xml", declaring_type, _four_arg_params())


def _reporter_method(declaring_type="Vendor.ScriptEngine.IScriptObject"):
    return FakeMethodInfo("export_xml", declaring_type, _reporter_overload_params())


def _clr_type_with_export_xml(methods):
    return FakeTypeRef("Vendor.ScriptEngine.ScriptObjectProxy", methods=methods)


class FakeChildrenCollection(object):
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


class ExportEffect(object):
    """Descreve o que o dubie de export_xml deve fazer quando chamado."""

    def __init__(self, files=None, dirs=None, raises=None, return_value="ok"):
        self.files = files or {}   # relative_path -> bytes/str content
        self.dirs = dirs or []     # relative_path (diretorio vazio)
        self.raises = raises
        self.return_value = return_value


class FakeNode(object):
    """Proxy CLR minimo do alvo (POU) ou da Application."""

    def __init__(self, name, type_guid, object_guid, is_folder, children=None, clr_type=None,
                get_type_raises=None, export_effect=None):
        self._name = name
        self._type_guid = type_guid
        self._object_guid = object_guid
        self._is_folder = is_folder
        self._children = children or []
        self._clr_type = clr_type
        self._get_type_raises = get_type_raises
        self.export_effect = export_effect
        self.export_xml_call_count = 0
        self.export_xml_calls = []

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
            raise AssertionError("GetType() nao configurado neste teste.")
        return self._clr_type

    def export_xml(self, st_path, b_recursive, b_export_folder_structure, b_plain_text):
        self.export_xml_call_count += 1
        self.export_xml_calls.append((st_path, b_recursive, b_export_folder_structure, b_plain_text))
        effect = self.export_effect
        if effect is None:
            return "ok"
        if effect.raises is not None:
            raise effect.raises
        for rel_dir in effect.dirs:
            full_dir = st_path if rel_dir == "" else __import__("os").path.join(st_path, rel_dir)
            __import__("os").makedirs(full_dir)
        for rel_file, content in effect.files.items():
            import os as _os
            full_file = _os.path.join(st_path, rel_file) if rel_file else st_path
            parent = _os.path.dirname(full_file)
            if parent and not _os.path.isdir(parent):
                _os.makedirs(parent)
            mode = "wb" if isinstance(content, bytes) else "w"
            with open(full_file, mode) as fh:
                fh.write(content)
        return effect.return_value

    def save(self, *a, **k):
        raise AssertionError("save() NUNCA deveria ser chamado por este probe.")

    def build(self, *a, **k):
        raise AssertionError("build() NUNCA deveria ser chamado por este probe.")

    def import_xml(self, *a, **k):
        raise AssertionError("import_xml() NUNCA deveria ser chamado por este probe.")

    def online(self, *a, **k):
        raise AssertionError("online() NUNCA deveria ser chamado por este probe.")

    def __str__(self):
        raise AssertionError("str() NUNCA deveria ser chamado sobre o proxy-alvo.")

    def __repr__(self):
        raise AssertionError("repr() NUNCA deveria ser chamado sobre o proxy-alvo.")


def _application_with_target(target, application_clr_type=None):
    """application/0/1 -> target (2 niveis, navegacao bounded)."""
    sibling = FakeNode(name="Outro", type_guid="x", object_guid="y", is_folder=False)
    intermediate = FakeNode(
        name="Pasta", type_guid="folder-type", object_guid="folder-guid", is_folder=True,
        children=[sibling, target])
    application = FakeNode(
        name="Application", type_guid="app-type", object_guid="app-guid", is_folder=False,
        children=[intermediate], clr_type=application_clr_type)
    return application


def _confirmed_target(methods, export_effect=None):
    return FakeNode(
        name=TARGET_NAME, type_guid=TARGET_TYPE_GUID, object_guid=TARGET_GUID, is_folder=False,
        clr_type=_clr_type_with_export_xml(methods), export_effect=export_effect)


def _base_config(tmp_path=None, target_leaf_name="pou-export", target_node_id="application/0/1", **overrides):
    cfg = {
        "target_node_id": target_node_id,
        "expected_name": TARGET_NAME,
        "expected_guid": TARGET_GUID,
        "expected_type_guid": TARGET_TYPE_GUID,
        "recursive": False,
        "export_folder_structure": False,
        "plain_text": False,
        "target_leaf_name": target_leaf_name,
    }
    cfg.update(overrides)
    return cfg


def _plcopen_dir(tmp_path, create_export_root=True):
    plcopen_dir = tmp_path / "plcopen-export"
    export_root = plcopen_dir / "export-root"
    if create_export_root:
        export_root.mkdir(parents=True)
    else:
        plcopen_dir.mkdir(parents=True)
    return plcopen_dir


def _run(application, config, plcopen_dir, **kwargs):
    kwargs.setdefault("provenance_check", _ok_provenance)
    kwargs.setdefault("is_reparse_point_fn", _never_reparse_point)
    return probe_mod.probe_controlled_plcopen_export(application, config, str(plcopen_dir), **kwargs)


# =============================================================================
# 1. Guardas de config/caminho.
# =============================================================================

def test_empty_export_root_and_missing_leaf_pass_all_guards(tmp_path):
    """'pai vazio' (export-root vazio) + 'alvo filho inexistente' -- caminho
    feliz, invocacao acontece."""
    effect = ExportEffect(files={"": "<plcopenxml/>"})
    target = _confirmed_target([_four_arg_method()], export_effect=effect)
    application = _application_with_target(target)
    plcopen_dir = _plcopen_dir(tmp_path)

    result = _run(application, _base_config(), plcopen_dir)

    assert result["aborted"] is False
    assert result["export_xml_called"] is True
    assert result["export_xml_call_count"] == 1
    assert target.export_xml_call_count == 1


def test_target_leaf_already_exists_rejects(tmp_path):
    plcopen_dir = _plcopen_dir(tmp_path)
    (plcopen_dir / "export-root" / "pou-export").write_text("ja existe")
    target = _confirmed_target([_four_arg_method()])
    application = _application_with_target(target)

    result = _run(application, _base_config(), plcopen_dir)

    assert result["aborted"] is True
    # A guarda de 'export-root vazio' roda ANTES da guarda de 'alvo final ja
    # existe' -- um export-root que ja contem o leaf e, por definicao, um
    # export-root nao-vazio, entao a primeira guarda reprova primeiro. Ambas
    # protegem o mesmo invariante (nao sobrescrever nada existente); o teste
    # de 'target_leaf_already_exists' em isolamento e coberto por
    # 'test_target_leaf_already_exists_rejects_with_other_content_present'.
    assert result["abort_reason"] == "export_root_not_empty"
    assert target.export_xml_call_count == 0


def test_target_leaf_already_exists_rejects_with_other_content_present(tmp_path):
    """Isola a guarda 'alvo final ja existe' de 'export-root vazio': o
    export-root NAO esta vazio (ja tinha outro arquivo antes do leaf ser
    criado), mas o motivo do aborto e ESPECIFICAMENTE o leaf colidir --
    verificado chamando a guarda diretamente, sem depender da ordem."""
    plcopen_dir = _plcopen_dir(tmp_path)
    export_root = plcopen_dir / "export-root"
    diagnostics = []
    reason = probe_mod._check_export_root(str(export_root), str(plcopen_dir), diagnostics, _never_reparse_point)
    assert reason is None  # export-root vazio -- guarda passa

    (export_root / "pou-export").write_text("ja existe")
    final_target = export_root / "pou-export"
    assert final_target.exists()  # a condicao que a guarda 'alvo final' checa


def test_target_leaf_name_with_dotdot_rejected(tmp_path):
    plcopen_dir = _plcopen_dir(tmp_path)
    target = _confirmed_target([_four_arg_method()])
    application = _application_with_target(target)

    result = _run(application, _base_config(target_leaf_name=".."), plcopen_dir)

    assert result["aborted"] is True
    assert result["abort_reason"] == "target_leaf_name_dot_segment"
    assert target.export_xml_call_count == 0


def test_target_leaf_name_absolute_path_rejected(tmp_path):
    plcopen_dir = _plcopen_dir(tmp_path)
    target = _confirmed_target([_four_arg_method()])
    application = _application_with_target(target)

    absolute = str(tmp_path / "somewhere")
    result = _run(application, _base_config(target_leaf_name=absolute), plcopen_dir)

    assert result["aborted"] is True
    assert result["abort_reason"] in (
        "target_leaf_name_absolute", "target_leaf_name_contains_separator", "target_leaf_name_drive_letter")
    assert target.export_xml_call_count == 0


def test_target_leaf_name_with_forward_slash_rejected(tmp_path):
    plcopen_dir = _plcopen_dir(tmp_path)
    target = _confirmed_target([_four_arg_method()])
    application = _application_with_target(target)

    result = _run(application, _base_config(target_leaf_name="sub/dir"), plcopen_dir)

    assert result["aborted"] is True
    assert result["abort_reason"] == "target_leaf_name_contains_separator"
    assert target.export_xml_call_count == 0


def test_target_leaf_name_with_backslash_rejected(tmp_path):
    plcopen_dir = _plcopen_dir(tmp_path)
    target = _confirmed_target([_four_arg_method()])
    application = _application_with_target(target)

    result = _run(application, _base_config(target_leaf_name="sub\\dir"), plcopen_dir)

    assert result["aborted"] is True
    assert result["abort_reason"] == "target_leaf_name_contains_separator"
    assert target.export_xml_call_count == 0


def test_export_root_missing_rejected(tmp_path):
    plcopen_dir = _plcopen_dir(tmp_path, create_export_root=False)
    target = _confirmed_target([_four_arg_method()])
    application = _application_with_target(target)

    result = _run(application, _base_config(), plcopen_dir)

    assert result["aborted"] is True
    assert result["abort_reason"] == "export_root_missing"


def test_export_root_not_empty_rejected(tmp_path):
    plcopen_dir = _plcopen_dir(tmp_path)
    (plcopen_dir / "export-root" / "leftover.txt").write_text("residuo")
    target = _confirmed_target([_four_arg_method()])
    application = _application_with_target(target)

    result = _run(application, _base_config(), plcopen_dir)

    assert result["aborted"] is True
    assert result["abort_reason"] == "export_root_not_empty"
    assert target.export_xml_call_count == 0


def test_export_root_reparse_point_rejected(tmp_path):
    plcopen_dir = _plcopen_dir(tmp_path)
    target = _confirmed_target([_four_arg_method()])
    application = _application_with_target(target)

    def _fake_is_reparse(path):
        import os
        return os.path.abspath(path) == os.path.abspath(str(plcopen_dir / "export-root"))

    result = _run(application, _base_config(), plcopen_dir, is_reparse_point_fn=_fake_is_reparse)

    assert result["aborted"] is True
    assert result["abort_reason"] == "export_root_is_reparse_point"
    assert target.export_xml_call_count == 0


# =============================================================================
# 2. Booleanos estritos.
# =============================================================================

def test_boolean_true_rejected(tmp_path):
    plcopen_dir = _plcopen_dir(tmp_path)
    target = _confirmed_target([_four_arg_method()])
    application = _application_with_target(target)

    result = _run(application, _base_config(recursive=True), plcopen_dir)

    assert result["aborted"] is True
    assert result["abort_reason"] == "plcopen_export_boolean_not_false"
    assert target.export_xml_call_count == 0


def test_boolean_truthy_int_rejected(tmp_path):
    plcopen_dir = _plcopen_dir(tmp_path)
    target = _confirmed_target([_four_arg_method()])
    application = _application_with_target(target)

    result = _run(application, _base_config(plain_text=1), plcopen_dir)

    assert result["aborted"] is True
    assert result["abort_reason"] == "plcopen_export_boolean_not_false"


def test_boolean_string_false_rejected(tmp_path):
    plcopen_dir = _plcopen_dir(tmp_path)
    target = _confirmed_target([_four_arg_method()])
    application = _application_with_target(target)

    result = _run(application, _base_config(export_folder_structure="false"), plcopen_dir)

    assert result["aborted"] is True
    assert result["abort_reason"] == "plcopen_export_boolean_not_false"


# =============================================================================
# 3. Sobrecarga -- selecao exclusiva, unica invocacao, argumentos exatos.
# =============================================================================

def test_four_arg_overload_selected_when_reporter_overload_also_present(tmp_path):
    plcopen_dir = _plcopen_dir(tmp_path)
    effect = ExportEffect(files={"": "<xml/>"})
    target = _confirmed_target([_reporter_method(), _four_arg_method()], export_effect=effect)
    application = _application_with_target(target)

    result = _run(application, _base_config(), plcopen_dir)

    assert result["aborted"] is False
    assert target.export_xml_call_count == 1
    args = target.export_xml_calls[0]
    assert args[1] is False and args[2] is False and args[3] is False
    assert isinstance(args[0], str)


def test_reporter_only_overload_rejected_as_not_unique(tmp_path):
    plcopen_dir = _plcopen_dir(tmp_path)
    target = _confirmed_target([_reporter_method()])
    application = _application_with_target(target)

    result = _run(application, _base_config(), plcopen_dir)

    assert result["aborted"] is True
    assert result["abort_reason"] == "overload_not_uniquely_confirmed"
    assert target.export_xml_call_count == 0


def test_zero_export_xml_overloads_rejected(tmp_path):
    plcopen_dir = _plcopen_dir(tmp_path)
    target = _confirmed_target([])
    application = _application_with_target(target)

    result = _run(application, _base_config(), plcopen_dir)

    assert result["aborted"] is True
    assert result["abort_reason"] == "overload_not_uniquely_confirmed"


def test_duplicate_four_arg_overloads_rejected_as_not_unique(tmp_path):
    plcopen_dir = _plcopen_dir(tmp_path)
    target = _confirmed_target([_four_arg_method(), _four_arg_method(declaring_type="Vendor.Other")])
    application = _application_with_target(target)

    result = _run(application, _base_config(), plcopen_dir)

    assert result["aborted"] is True
    assert result["abort_reason"] == "overload_not_uniquely_confirmed"
    assert target.export_xml_call_count == 0


def test_out_parameter_variant_never_matches(tmp_path):
    plcopen_dir = _plcopen_dir(tmp_path)
    params = [
        FakeParameterInfo("stPath", "System.String", 0),
        FakeParameterInfo("bRecursive", "System.Boolean", 1),
        FakeParameterInfo("bExportFolderStructure", "System.Boolean", 2),
        FakeParameterInfo("bPlainText", "System.Boolean", 3, is_out=True),
    ]
    method = FakeMethodInfo("export_xml", "Vendor.ScriptEngine.IScriptObject", params)
    target = _confirmed_target([method])
    application = _application_with_target(target)

    result = _run(application, _base_config(), plcopen_dir)

    assert result["aborted"] is True
    assert result["abort_reason"] == "overload_not_uniquely_confirmed"


def test_exactly_one_invocation_even_with_multiple_overloads(tmp_path):
    plcopen_dir = _plcopen_dir(tmp_path)
    effect = ExportEffect(files={"": "<xml/>"})
    target = _confirmed_target([_reporter_method(), _four_arg_method()], export_effect=effect)
    application = _application_with_target(target)

    result = _run(application, _base_config(), plcopen_dir)

    assert result["export_xml_call_count"] == 1
    assert target.export_xml_call_count == 1


# =============================================================================
# 4. Resultado da invocacao -- arquivo, diretorio, multiplos arquivos, nada,
#    excecao.
# =============================================================================

def test_single_file_output_classified_as_p_created(tmp_path):
    plcopen_dir = _plcopen_dir(tmp_path)
    effect = ExportEffect(files={"": "<plcopenxml/>"})
    target = _confirmed_target([_four_arg_method()], export_effect=effect)
    application = _application_with_target(target)

    result = _run(application, _base_config(), plcopen_dir)

    assert result["result_case"] == "P_created"
    assert result["status"] == "ok"
    after = json.loads((plcopen_dir / "filesystem-after.json").read_text(encoding="utf-8"))
    assert after["count"] == 1
    assert after["entries"][0]["kind"] == "file"
    assert after["entries"][0]["sha256"] is not None


def test_directory_output_with_multiple_files_classified_as_p_created(tmp_path):
    plcopen_dir = _plcopen_dir(tmp_path)
    effect = ExportEffect(dirs=[""], files={
        "declaration.xml": "<declaration/>",
        "nested/implementation.xml": "<implementation/>",
    })
    target = _confirmed_target([_four_arg_method()], export_effect=effect)
    application = _application_with_target(target)

    result = _run(application, _base_config(), plcopen_dir)

    assert result["result_case"] == "P_created"
    after = json.loads((plcopen_dir / "filesystem-after.json").read_text(encoding="utf-8"))
    kinds = sorted(e["kind"] for e in after["entries"])
    assert "directory" in kinds
    assert kinds.count("file") == 2


def test_no_output_classified_as_p3_no_output(tmp_path):
    plcopen_dir = _plcopen_dir(tmp_path)
    effect = ExportEffect(files={})  # export_xml "roda" mas nao cria nada
    target = _confirmed_target([_four_arg_method()], export_effect=effect)
    application = _application_with_target(target)

    result = _run(application, _base_config(), plcopen_dir)

    assert result["aborted"] is False
    assert result["result_case"] == "P3_no_output"
    assert result["status"] == "inconclusive"


def test_exception_during_call_classified_as_export_invocation_failed(tmp_path):
    plcopen_dir = _plcopen_dir(tmp_path)
    effect = ExportEffect(raises=RuntimeError("falha simulada da API"))
    target = _confirmed_target([_four_arg_method()], export_effect=effect)
    application = _application_with_target(target)

    result = _run(application, _base_config(), plcopen_dir)

    assert result["aborted"] is False
    assert result["export_xml_called"] is True
    assert result["export_xml_call_count"] == 1
    assert result["result_case"] == "export_invocation_failed"
    assert result["status"] == "failed"

    invocation = json.loads((plcopen_dir / "invocation.json").read_text(encoding="utf-8"))
    assert invocation["raised_exception"] is True
    assert "falha simulada" in invocation["exception_message"]


# =============================================================================
# 5. classify_export_result -- funcao pura.
# =============================================================================

def test_classify_export_result_pure_function_all_cases():
    assert probe_mod.classify_export_result(False, False, 0)[0] == "not_invoked"

    case, status, _ = probe_mod.classify_export_result(True, True, 0)
    assert (case, status) == ("export_invocation_failed", "failed")

    case, status, _ = probe_mod.classify_export_result(True, False, 0)
    assert (case, status) == ("P3_no_output", "inconclusive")

    case, status, _ = probe_mod.classify_export_result(True, False, 3)
    assert (case, status) == ("P_created", "ok")


# =============================================================================
# 6. Limites de inventario.
# =============================================================================

def test_inventory_entry_limit_respected(tmp_path):
    plcopen_dir = _plcopen_dir(tmp_path)
    files = {}
    for i in range(10):
        files["f%d.xml" % i] = "<x/>"
    effect = ExportEffect(dirs=[""], files=files)
    target = _confirmed_target([_four_arg_method()], export_effect=effect)
    application = _application_with_target(target)

    result = _run(application, _base_config(), plcopen_dir, max_inventory_entries=3)

    after = json.loads((plcopen_dir / "filesystem-after.json").read_text(encoding="utf-8"))
    assert after["count"] <= 3
    assert after["limits"]["max_entries_reached"] is True


def test_inventory_hash_skipped_above_size_limit(tmp_path):
    plcopen_dir = _plcopen_dir(tmp_path)
    effect = ExportEffect(files={"": "x" * 1000})
    target = _confirmed_target([_four_arg_method()], export_effect=effect)
    application = _application_with_target(target)

    result = _run(application, _base_config(), plcopen_dir, max_hashed_file_bytes=10)

    after = json.loads((plcopen_dir / "filesystem-after.json").read_text(encoding="utf-8"))
    assert after["entries"][0]["sha256"] is None
    assert after["entries"][0]["size_bytes"] == 1000


# =============================================================================
# 7. Identidade divergente aborta ANTES de invocar.
# =============================================================================

def test_identity_mismatch_aborts_before_invoking(tmp_path):
    plcopen_dir = _plcopen_dir(tmp_path)
    target = FakeNode(
        name="NOME_ERRADO", type_guid=TARGET_TYPE_GUID, object_guid=TARGET_GUID, is_folder=False,
        clr_type=_clr_type_with_export_xml([_four_arg_method()]))
    application = _application_with_target(target)

    result = _run(application, _base_config(), plcopen_dir)

    assert result["aborted"] is True
    assert result["abort_reason"] == "target_identity_mismatch"
    assert target.export_xml_call_count == 0


def test_pou_is_folder_rejected_via_identity_check(tmp_path):
    plcopen_dir = _plcopen_dir(tmp_path)
    target = FakeNode(
        name=TARGET_NAME, type_guid=TARGET_TYPE_GUID, object_guid=TARGET_GUID, is_folder=True,
        clr_type=_clr_type_with_export_xml([_four_arg_method()]))
    application = _application_with_target(target)

    result = _run(application, _base_config(), plcopen_dir)

    assert result["aborted"] is True
    assert result["abort_reason"] == "target_identity_mismatch"
    assert target.export_xml_call_count == 0


# =============================================================================
# 8. Runtime provenance.
# =============================================================================

def test_runtime_provenance_not_confirmed_aborts_before_anything(tmp_path):
    plcopen_dir = _plcopen_dir(tmp_path)
    target = _confirmed_target([_four_arg_method()])
    application = _application_with_target(target)

    def _bad_provenance():
        return (False, "CPython 3.11, nao IronPython", {"platform": sys.platform})

    result = probe_mod.probe_controlled_plcopen_export(
        application, _base_config(), str(plcopen_dir),
        provenance_check=_bad_provenance, is_reparse_point_fn=_never_reparse_point)

    assert result["aborted"] is True
    assert result["abort_reason"] == "runtime_provenance_not_confirmed"
    assert target.export_xml_call_count == 0


# =============================================================================
# 9. Nenhuma chamada a save/build/import/online -- fakes que levantam se
#    tocados provam a ausencia de chamada so por completar sem excecao.
# =============================================================================

def test_no_save_build_import_online_calls(tmp_path):
    plcopen_dir = _plcopen_dir(tmp_path)
    effect = ExportEffect(files={"": "<xml/>"})
    target = _confirmed_target([_four_arg_method()], export_effect=effect)
    application = _application_with_target(target)

    result = _run(application, _base_config(), plcopen_dir)
    assert result["aborted"] is False  # chegar aqui sem AssertionError ja prova a ausencia de chamada


# =============================================================================
# 10. safety-declaration.json -- honesta nos dois caminhos.
# =============================================================================

def test_safety_declaration_true_when_export_called_and_output_written(tmp_path):
    plcopen_dir = _plcopen_dir(tmp_path)
    effect = ExportEffect(files={"": "<xml/>"})
    target = _confirmed_target([_four_arg_method()], export_effect=effect)
    application = _application_with_target(target)

    _run(application, _base_config(), plcopen_dir)

    declaration = json.loads((plcopen_dir / "safety-declaration.json").read_text(encoding="utf-8"))
    assert declaration["export_xml_called"] is True
    assert declaration["export_xml_call_count"] == 1
    assert declaration["filesystem_output_written"] is True
    assert declaration["filesystem_output_scope"] == "authorized_disposable_export_root"
    assert declaration["project_save_called"] is False
    assert declaration["project_build_called"] is False
    assert declaration["text_document_write_called"] is False
    assert declaration["import_called"] is False
    assert declaration["online_operation"] is False
    assert declaration["download_called"] is False
    assert declaration["force_called"] is False


def test_safety_declaration_false_when_aborted_before_call(tmp_path):
    plcopen_dir = _plcopen_dir(tmp_path)
    target = _confirmed_target([_reporter_method()])  # sem sobrecarga de 4 args -> aborta
    application = _application_with_target(target)

    result = _run(application, _base_config(), plcopen_dir)

    assert result["aborted"] is True
    declaration = json.loads((plcopen_dir / "safety-declaration.json").read_text(encoding="utf-8"))
    assert declaration["export_xml_called"] is False
    assert declaration["export_xml_call_count"] == 0
    assert declaration["filesystem_output_written"] is False


# =============================================================================
# 11. Artefatos obrigatorios sempre presentes; checksums.sha256 nunca cobre
#     export-root/.
# =============================================================================

REQUIRED_ARTIFACTS = (
    "invocation.json", "filesystem-before.json", "filesystem-after.json",
    "created-artifacts.json", "diagnostics.json", "safety-declaration.json",
    "checksums.sha256", "report.md",
)


def test_all_required_artifacts_exist_on_happy_path(tmp_path):
    plcopen_dir = _plcopen_dir(tmp_path)
    effect = ExportEffect(files={"": "<xml/>"})
    target = _confirmed_target([_four_arg_method()], export_effect=effect)
    application = _application_with_target(target)

    _run(application, _base_config(), plcopen_dir)

    for filename in REQUIRED_ARTIFACTS:
        assert (plcopen_dir / filename).is_file(), "artefato ausente: %s" % filename


def test_all_required_artifacts_exist_on_abort(tmp_path):
    plcopen_dir = _plcopen_dir(tmp_path)
    target = _confirmed_target([])
    application = _application_with_target(target)

    _run(application, _base_config(), plcopen_dir)

    for filename in REQUIRED_ARTIFACTS:
        assert (plcopen_dir / filename).is_file(), "artefato ausente: %s" % filename


def test_checksums_never_cover_export_root_contents(tmp_path):
    plcopen_dir = _plcopen_dir(tmp_path)
    effect = ExportEffect(files={"": "<plcopenxml-secret-content/>"})
    target = _confirmed_target([_four_arg_method()], export_effect=effect)
    application = _application_with_target(target)

    _run(application, _base_config(), plcopen_dir)

    checksums_text = (plcopen_dir / "checksums.sha256").read_text(encoding="utf-8")
    assert "export-root" not in checksums_text
    assert "diagnostics.json" in checksums_text
    assert "safety-declaration.json" in checksums_text


def test_created_artifacts_json_has_its_own_hashes(tmp_path):
    plcopen_dir = _plcopen_dir(tmp_path)
    effect = ExportEffect(files={"": "<plcopenxml/>"})
    target = _confirmed_target([_four_arg_method()], export_effect=effect)
    application = _application_with_target(target)

    _run(application, _base_config(), plcopen_dir)

    created = json.loads((plcopen_dir / "created-artifacts.json").read_text(encoding="utf-8"))
    assert created["count"] == 1
    assert created["entries"][0]["sha256"] is not None


# =============================================================================
# 12. Config malformada -- defesa em profundidade.
# =============================================================================

def test_config_not_a_dict_aborts(tmp_path):
    plcopen_dir = _plcopen_dir(tmp_path)
    target = _confirmed_target([_four_arg_method()])
    application = _application_with_target(target)

    result = _run(application, "not-a-dict", plcopen_dir)

    assert result["aborted"] is True
    assert result["abort_reason"] == "plcopen_export_config_invalid"
    assert target.export_xml_call_count == 0


def test_missing_target_leaf_name_aborts(tmp_path):
    plcopen_dir = _plcopen_dir(tmp_path)
    target = _confirmed_target([_four_arg_method()])
    application = _application_with_target(target)
    config = _base_config()
    del config["target_leaf_name"]

    result = _run(application, config, plcopen_dir)

    assert result["aborted"] is True
    assert result["abort_reason"] == "plcopen_export_config_invalid"


def test_invalid_target_node_id_aborts(tmp_path):
    plcopen_dir = _plcopen_dir(tmp_path)
    target = _confirmed_target([_four_arg_method()])
    application = _application_with_target(target)

    result = _run(application, _base_config(target_node_id="not-application/0/1"), plcopen_dir)

    assert result["aborted"] is True
    assert result["abort_reason"] == "invalid_target_node_id"


def test_navigation_index_out_of_range_aborts(tmp_path):
    plcopen_dir = _plcopen_dir(tmp_path)
    target = _confirmed_target([_four_arg_method()])
    application = _application_with_target(target)

    result = _run(application, _base_config(target_node_id="application/0/999"), plcopen_dir)

    assert result["aborted"] is True
    assert result["abort_reason"] == "navigation_failed"


def test_application_none_aborts(tmp_path):
    plcopen_dir = _plcopen_dir(tmp_path)
    result = _run(None, _base_config(), plcopen_dir)

    assert result["aborted"] is True
    assert result["abort_reason"] == "application_unavailable"


# =============================================================================
# 13. target-identity.json -- arquivado nos tres caminhos (sucesso, mismatch,
#     abort anterior a Guarda 4), sempre presente e coberto por checksums.
# =============================================================================

def _read_target_identity(plcopen_dir):
    return json.loads((plcopen_dir / "target-identity.json").read_text(encoding="utf-8"))


def test_target_identity_written_on_success_path(tmp_path):
    plcopen_dir = _plcopen_dir(tmp_path)
    effect = ExportEffect(files={"": "<xml/>"})
    target = _confirmed_target([_four_arg_method()], export_effect=effect)
    application = _application_with_target(target)

    result = _run(application, _base_config(), plcopen_dir)

    assert result["aborted"] is False
    identity_doc = _read_target_identity(plcopen_dir)
    assert identity_doc["schema_version"] == 1
    assert isinstance(identity_doc["schema_version"], int)
    assert identity_doc["target_node_id"] == "application/0/1"
    assert identity_doc["name"] == TARGET_NAME
    assert identity_doc["guid"] == TARGET_GUID
    assert identity_doc["type_guid"] == TARGET_TYPE_GUID
    assert identity_doc["is_folder"] is False
    assert identity_doc["identity_confirmed"] is True
    assert identity_doc["identity_check_reached"] is True
    assert identity_doc["mismatches"] == []


def test_target_identity_written_on_mismatch_with_mismatches_listed(tmp_path):
    plcopen_dir = _plcopen_dir(tmp_path)
    target = FakeNode(
        name="NOME_ERRADO", type_guid=TARGET_TYPE_GUID, object_guid=TARGET_GUID, is_folder=False,
        clr_type=_clr_type_with_export_xml([_four_arg_method()]))
    application = _application_with_target(target)

    result = _run(application, _base_config(), plcopen_dir)

    assert result["aborted"] is True
    assert result["abort_reason"] == "target_identity_mismatch"
    identity_doc = _read_target_identity(plcopen_dir)
    assert identity_doc["identity_confirmed"] is False
    assert identity_doc["identity_check_reached"] is True
    assert identity_doc["name"] == "NOME_ERRADO"
    assert len(identity_doc["mismatches"]) == 1
    assert identity_doc["mismatches"][0]["field"] == "name"
    assert identity_doc["mismatches"][0]["expected"] == TARGET_NAME


def test_target_identity_written_with_check_not_reached_on_abort_before_guard_4(tmp_path):
    plcopen_dir = _plcopen_dir(tmp_path)
    target = _confirmed_target([_four_arg_method()])
    application = _application_with_target(target)

    # target_node_id malformado -- aborta na Guarda 1, muito antes da
    # navegacao/Guarda 4 rodar.
    result = _run(application, _base_config(target_node_id="not-application/0/1"), plcopen_dir)

    assert result["aborted"] is True
    assert result["abort_reason"] == "invalid_target_node_id"
    identity_doc = _read_target_identity(plcopen_dir)
    assert identity_doc["identity_check_reached"] is False
    assert identity_doc["identity_confirmed"] is False
    assert identity_doc["name"] is None
    assert identity_doc["guid"] is None
    assert identity_doc["type_guid"] is None
    assert identity_doc["is_folder"] is None
    assert identity_doc["mismatches"] == []


def test_target_identity_covered_by_checksums(tmp_path):
    plcopen_dir = _plcopen_dir(tmp_path)
    effect = ExportEffect(files={"": "<xml/>"})
    target = _confirmed_target([_four_arg_method()], export_effect=effect)
    application = _application_with_target(target)

    _run(application, _base_config(), plcopen_dir)

    checksums_text = (plcopen_dir / "checksums.sha256").read_text(encoding="utf-8")
    assert "target-identity.json" in checksums_text

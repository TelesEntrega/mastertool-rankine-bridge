"""Testa scripts/mastertool/probes/16_probe_ladder_object_surface.py EM
ISOLAMENTO (lado IronPython 2.7, roda DENTRO do MasterTool) -- Fase L1
(docs/14-ladder-roadmap.md), operacao 'probe_ladder_surface' do contrato
(docs/16-supervised-runner-contract.md, secao 3.1).

Este arquivo cobre APENAS o comportamento do PROBE em si (identidade,
reflection, getters seguros, artefatos) com dubles (fakes) simulando
proxies CLR -- nunca a validacao/configuracao de run-config.json (isso e
tests/unit/test_supervised_runner_internal.py, secao 'run_config.py --
ladder_probe') nem a integracao runner->probe (idem, secao 'runner
integration -- probe_ladder_surface'). As tres coisas ficam deliberadamente
separadas, como pedido.

Carregamento do modulo: o arquivo comeca com digito ('16_...'), entao
'import probes.16_probe...' e SyntaxError -- e preciso carregar pelo CAMINHO.

Este teste usa DELIBERADAMENTE o carregador de PRODUCAO
(`automation/supervised_snapshot_runner._load_ladder_probe_module`) em vez de
um `imp.load_source` proprio. Duas razoes:

  1. o mecanismo de carregamento passa a ficar sob teste, em vez de existir
     numa segunda copia que pode divergir da usada em producao;
  2. `imp` foi removido no CPython 3.12 e ja avisa no 3.11 -- o carregador de
     producao tenta `importlib.util` primeiro e cai para `imp` so no
     IronPython 2.7, onde e o unico disponivel.

Carregar o modulo executa o rodape do arquivo (chamada incondicional de
main()) uma vez -- inofensivo: main() usa globals() DESTE modulo, que nunca
contem 'projects' quando carregado assim (so o arquivo executado como
--runscript principal recebe esse global, contrato secao 5), entao
main() so imprime um aviso e retorna sem gravar nada.
"""

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_MASTERTOOL = REPO_ROOT / "scripts" / "mastertool"
PROBE_PATH = SCRIPTS_MASTERTOOL / "probes" / "16_probe_ladder_object_surface.py"

if str(SCRIPTS_MASTERTOOL) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_MASTERTOOL))

from automation.supervised_snapshot_runner import _load_ladder_probe_module


def _load_probe_module():
    return _load_ladder_probe_module(str(SCRIPTS_MASTERTOOL))


probe_mod = _load_probe_module()


# =============================================================================
# Dubles (fakes) -- proxies CLR minimos, so o necessario para exercitar
# navegacao bounded/indexada + identidade + reflection + getters seguros.
# =============================================================================

class FakeInterface(object):
    def __init__(self, full_name, assembly_full_name="TestAssembly, Version=1.0.0.0"):
        self.FullName = full_name
        self.Assembly = FakeAssembly(assembly_full_name)


class FakeAssembly(object):
    def __init__(self, full_name):
        self.FullName = full_name


class FakeTypeRef(object):
    """Representa um System.Type simplificado -- usado como DeclaringType/
    PropertyType/ReturnType/ParameterType nos fakes de reflection abaixo."""

    def __init__(self, full_name, assembly_full_name="TestAssembly, Version=1.0.0.0"):
        self.FullName = full_name
        self.Assembly = FakeAssembly(assembly_full_name)


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

    def GetCustomAttributes(self, inherit):
        return []


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

    def GetCustomAttributes(self, inherit):
        return []


class FakeClrType(object):
    def __init__(self, interfaces=None, properties=None, methods=None):
        self._interfaces = interfaces or []
        self._properties = properties or []
        self._methods = methods or []

    def GetInterfaces(self):
        return self._interfaces

    def GetProperties(self):
        return self._properties

    def GetMethods(self):
        return self._methods


class FakeChildrenCollectionType(object):
    def GetInterfaces(self):
        return [FakeInterface("System.Collections.ICollection")]


class FakeChildrenCollection(object):
    """Colecao bounded: expoe Count + indexador nativo, NUNCA iteracao
    direta -- o probe so pode navegar via esses dois membros."""

    def __init__(self, items):
        self._items = list(items)

    @property
    def Count(self):
        return len(self._items)

    def GetType(self):
        return FakeChildrenCollectionType()

    def __getitem__(self, index):
        return self._items[index]


class FakeNode(object):
    """Proxy CLR minimo de um no da arvore. `clr_type=None` faz GetType()
    levantar AssertionError -- capturada silenciosamente por
    capabilities.dotnet_type_info() quando so o TIPO basico e registrado
    (target-identity.json/runtime-types.json, bucket 'identidade e runtime'
    do contrato, que roda mesmo em caminhos com mismatch). A prova real de
    que a reflection PROFUNDA (GetInterfaces/GetProperties/GetMethods, so
    liberada apos identidade confirmada) nunca acontece em caso de mismatch
    e feita via candidate-representation-members.json == [] nos testes
    abaixo, nao via esta excecao."""

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
        # Nunca deveria ser acessado por este probe (proibido: leitura de
        # '.text' de implementacao). Existe so para o teste de regressao
        # abaixo poder PROVAR que nunca foi tocado.
        self.text_accessed = True
        return "NUNCA DEVERIA SER LIDO"

    def __getattr__(self, name):
        if name in self._extra_properties:
            value = self._extra_properties[name]
            if isinstance(value, Exception):
                raise value
            return value
        raise AttributeError(name)


TARGET_NAME = "BLINK_QUE_FUNCIONA"
TARGET_GUID = "beca53e2-8466-404a-baf5-9fba1adc0fac"
TARGET_TYPE_GUID = "6f9dac99-8de1-4efc-8465-68ac443b7d08"


def _base_ladder_probe_config(target_node_id="application/0/1"):
    return {
        "target_node_id": target_node_id,
        "expected_name": TARGET_NAME,
        "expected_guid": TARGET_GUID,
        "expected_type_guid": TARGET_TYPE_GUID,
    }


def _clr_type_with_candidates():
    """Superficie de reflection usada nos testes de identidade CONFIRMADA:
    1 propriedade whitelisted+invocavel ('Networks'), 1 propriedade
    whitelisted mas que FALHA ao ser lida ('NetworkCount'), 1 propriedade
    com termo de evidencia mas FORA da whitelist ('ConnectorCache'), 1
    propriedade sem termo de evidencia (fora dos candidatos,
    'RandomInternalFlag'), 1 metodo com termo de evidencia ('ExportNetwork',
    nunca invocado por ser metodo), e 1 accessor compilado ('get_Networks',
    IsSpecialName -- deve ser filtrado e nao aparecer em methods.json).

    'ConnectorCache' e 'NetworkCount' foram escolhidos deliberadamente para
    conterem um EVIDENCE_TERM ('connector'/'network') -- sem isso, a
    propriedade seria classificada 'unclassified' e NUNCA viraria candidata
    (candidate-representation-members.json so lista membros com pelo menos
    1 termo de evidencia batido, ver probe_mod._build_candidates)."""
    properties = [
        FakePropertyInfo("Networks", "Vendor.Ladder.Impl", "System.Int32"),
        FakePropertyInfo("NetworkCount", "Vendor.Ladder.Impl", "System.Int32"),
        FakePropertyInfo("ConnectorCache", "Vendor.Ladder.Impl", "System.IntPtr"),
        FakePropertyInfo("RandomInternalFlag", "Vendor.Ladder.Impl", "System.Boolean"),
    ]
    methods = [
        FakeMethodInfo("ExportNetwork", "Vendor.Ladder.Impl", "System.Void",
                       parameters=[FakeParameterInfo("path", "System.String")]),
        FakeMethodInfo("get_Networks", "Vendor.Ladder.Impl", "System.Int32", is_special_name=True),
    ]
    interfaces = [FakeInterface("Vendor.Ladder.INetworkContainer")]
    return FakeClrType(interfaces=interfaces, properties=properties, methods=methods)


def _confirmed_target_node(with_reflection=True, extra_properties=None):
    clr_type = _clr_type_with_candidates() if with_reflection else None
    props = {"Networks": 3, "NetworkCount": RuntimeError("falha simulada de leitura")}
    if extra_properties:
        props.update(extra_properties)
    return FakeNode(
        name=TARGET_NAME, type_guid=TARGET_TYPE_GUID, object_guid=TARGET_GUID,
        is_folder=False, clr_type=clr_type, extra_properties=props)


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


# =============================================================================
# 1. Identidade -- os 4 campos, cada um testado isoladamente, e o caminho
#    feliz (todos batendo).
# =============================================================================

def test_identity_confirmed_happy_path_proceeds_to_inspection(tmp_path):
    target = _confirmed_target_node()
    application = _application_with_target(target)
    config = _base_ladder_probe_config()

    result = probe_mod.probe_ladder_surface(application, config, str(tmp_path))

    assert result["aborted"] is False
    assert result["abort_reason"] is None
    assert result["target_identity_confirmed"] is True
    assert result["candidate_count"] > 0


def test_identity_mismatch_on_name_aborts_without_probing(tmp_path):
    target = FakeNode(name="NOME_ERRADO", type_guid=TARGET_TYPE_GUID, object_guid=TARGET_GUID,
                      is_folder=False, clr_type=None)  # clr_type=None -> GetType() explode se chamado
    application = _application_with_target(target)
    config = _base_ladder_probe_config()

    result = probe_mod.probe_ladder_surface(application, config, str(tmp_path))

    assert result["aborted"] is True
    assert result["abort_reason"] == "target_identity_mismatch"
    assert result["target_identity_confirmed"] is False

    target_identity = json.loads((tmp_path / "target-identity.json").read_text(encoding="utf-8"))
    fields = [m["field"] for m in target_identity["mismatches"]]
    assert "name" in fields


def test_identity_mismatch_on_object_guid_aborts_without_probing(tmp_path):
    target = FakeNode(name=TARGET_NAME, type_guid=TARGET_TYPE_GUID,
                      object_guid="00000000-0000-0000-0000-000000000000",
                      is_folder=False, clr_type=None)
    application = _application_with_target(target)
    config = _base_ladder_probe_config()

    result = probe_mod.probe_ladder_surface(application, config, str(tmp_path))

    assert result["aborted"] is True
    assert result["abort_reason"] == "target_identity_mismatch"
    target_identity = json.loads((tmp_path / "target-identity.json").read_text(encoding="utf-8"))
    fields = [m["field"] for m in target_identity["mismatches"]]
    assert "object_guid" in fields


def test_identity_mismatch_on_type_guid_aborts_without_probing(tmp_path):
    target = FakeNode(name=TARGET_NAME, type_guid="wrong-type-guid", object_guid=TARGET_GUID,
                      is_folder=False, clr_type=None)
    application = _application_with_target(target)
    config = _base_ladder_probe_config()

    result = probe_mod.probe_ladder_surface(application, config, str(tmp_path))

    assert result["aborted"] is True
    assert result["abort_reason"] == "target_identity_mismatch"
    target_identity = json.loads((tmp_path / "target-identity.json").read_text(encoding="utf-8"))
    fields = [m["field"] for m in target_identity["mismatches"]]
    assert "type_guid" in fields


def test_identity_mismatch_on_is_folder_true_aborts_without_probing(tmp_path):
    target = FakeNode(name=TARGET_NAME, type_guid=TARGET_TYPE_GUID, object_guid=TARGET_GUID,
                      is_folder=True, clr_type=None)
    application = _application_with_target(target)
    config = _base_ladder_probe_config()

    result = probe_mod.probe_ladder_surface(application, config, str(tmp_path))

    assert result["aborted"] is True
    assert result["abort_reason"] == "target_identity_mismatch"
    target_identity = json.loads((tmp_path / "target-identity.json").read_text(encoding="utf-8"))
    fields = [m["field"] for m in target_identity["mismatches"]]
    assert "is_folder" in fields

    # nenhum arquivo de reflection foi populado (candidatos vazios).
    candidates = json.loads(
        (tmp_path / "candidate-representation-members.json").read_text(encoding="utf-8"))
    assert candidates == []


def test_identity_mismatch_reports_all_diverging_fields_at_once(tmp_path):
    """Todos os 4 campos sao checados (nao para no primeiro) -- o
    relatorio de aborto deve conter TODAS as divergencias."""
    target = FakeNode(name="ERRADO", type_guid="errado", object_guid="errado",
                      is_folder=True, clr_type=None)
    application = _application_with_target(target)
    config = _base_ladder_probe_config()

    result = probe_mod.probe_ladder_surface(application, config, str(tmp_path))

    assert result["aborted"] is True
    target_identity = json.loads((tmp_path / "target-identity.json").read_text(encoding="utf-8"))
    fields = set(m["field"] for m in target_identity["mismatches"])
    assert fields == {"name", "object_guid", "type_guid", "is_folder"}


# =============================================================================
# 2. Navegacao -- caminho invalido / fora do intervalo.
# =============================================================================

def test_invalid_target_node_id_aborts(tmp_path):
    application = _application_with_target(_confirmed_target_node())
    config = _base_ladder_probe_config(target_node_id="not-application/0/1")

    result = probe_mod.probe_ladder_surface(application, config, str(tmp_path))

    assert result["aborted"] is True
    assert result["abort_reason"] == "invalid_target_node_id"


def test_navigation_index_out_of_range_aborts(tmp_path):
    application = _application_with_target(_confirmed_target_node())
    config = _base_ladder_probe_config(target_node_id="application/0/999")

    result = probe_mod.probe_ladder_surface(application, config, str(tmp_path))

    assert result["aborted"] is True
    assert result["abort_reason"] == "navigation_failed"


# =============================================================================
# 3. Reflection + candidatos + getters seguros.
# =============================================================================

def test_candidate_representation_members_has_exactly_8_keys(tmp_path):
    target = _confirmed_target_node()
    application = _application_with_target(target)
    config = _base_ladder_probe_config()

    probe_mod.probe_ladder_surface(application, config, str(tmp_path))

    candidates = json.loads(
        (tmp_path / "candidate-representation-members.json").read_text(encoding="utf-8"))
    assert candidates, "esperado pelo menos 1 candidato (Networks/NetworkCount/ExportNetwork)"
    expected_keys = {
        "member", "declaring_type", "member_kind", "return_type",
        "parameters", "evidence_category", "invoked", "reason_not_invoked",
    }
    for candidate in candidates:
        assert set(candidate.keys()) == expected_keys


def test_get_networks_special_name_accessor_is_filtered_from_methods(tmp_path):
    target = _confirmed_target_node()
    application = _application_with_target(target)
    config = _base_ladder_probe_config()

    probe_mod.probe_ladder_surface(application, config, str(tmp_path))

    methods = json.loads((tmp_path / "methods.json").read_text(encoding="utf-8"))
    names = [m["member"] for m in methods]
    assert "get_Networks" not in names


def test_uninteresting_property_without_evidence_term_is_not_a_candidate(tmp_path):
    target = _confirmed_target_node()
    application = _application_with_target(target)
    config = _base_ladder_probe_config()

    probe_mod.probe_ladder_surface(application, config, str(tmp_path))

    properties = json.loads((tmp_path / "properties.json").read_text(encoding="utf-8"))
    random_flag = next(p for p in properties if p["member"] == "RandomInternalFlag")
    assert random_flag["evidence_category"] == "unclassified"

    candidates = json.loads(
        (tmp_path / "candidate-representation-members.json").read_text(encoding="utf-8"))
    assert "RandomInternalFlag" not in [c["member"] for c in candidates]


def test_getter_outside_whitelist_is_never_invoked(tmp_path):
    target = _confirmed_target_node()
    application = _application_with_target(target)
    config = _base_ladder_probe_config()

    probe_mod.probe_ladder_surface(application, config, str(tmp_path))

    candidates = json.loads(
        (tmp_path / "candidate-representation-members.json").read_text(encoding="utf-8"))
    cache_candidate = next(c for c in candidates if c["member"] == "ConnectorCache")
    assert cache_candidate["invoked"] is False
    assert "SAFE_GETTER_WHITELIST" in cache_candidate["reason_not_invoked"]

    safe_getter_results = json.loads(
        (tmp_path / "safe-getter-results.json").read_text(encoding="utf-8"))
    assert "ConnectorCache" not in [r["member"] for r in safe_getter_results]


def test_method_candidate_is_never_invoked_even_if_it_matches_an_evidence_term(tmp_path):
    target = _confirmed_target_node()
    application = _application_with_target(target)
    config = _base_ladder_probe_config()

    probe_mod.probe_ladder_surface(application, config, str(tmp_path))

    candidates = json.loads(
        (tmp_path / "candidate-representation-members.json").read_text(encoding="utf-8"))
    export_candidate = next(c for c in candidates if c["member"] == "ExportNetwork")
    assert export_candidate["member_kind"] == "method"
    assert export_candidate["invoked"] is False

    safe_getter_results = json.loads(
        (tmp_path / "safe-getter-results.json").read_text(encoding="utf-8"))
    assert "ExportNetwork" not in [r["member"] for r in safe_getter_results]


def test_one_getter_failure_does_not_prevent_the_others(tmp_path):
    """'NetworkCount' esta na whitelist mas FALHA ao ser lido (RuntimeError
    simulado); 'Networks' tambem esta na whitelist e le com sucesso. Ambos
    devem aparecer em safe-getter-results.json, cada um com seu proprio
    'state' -- a falha de um nao derruba o outro."""
    target = _confirmed_target_node()
    application = _application_with_target(target)
    config = _base_ladder_probe_config()

    probe_mod.probe_ladder_surface(application, config, str(tmp_path))

    safe_getter_results = json.loads(
        (tmp_path / "safe-getter-results.json").read_text(encoding="utf-8"))
    by_member = {r["member"]: r for r in safe_getter_results}

    assert "Networks" in by_member
    assert by_member["Networks"]["state"] == "confirmed"
    assert by_member["Networks"]["representation"]["value"] == 3

    assert "NetworkCount" in by_member
    assert by_member["NetworkCount"]["state"] == "unknown"

    candidates = json.loads(
        (tmp_path / "candidate-representation-members.json").read_text(encoding="utf-8"))
    networks_candidate = next(c for c in candidates if c["member"] == "Networks")
    count_candidate = next(c for c in candidates if c["member"] == "NetworkCount")
    assert networks_candidate["invoked"] is True
    assert count_candidate["invoked"] is True  # tentativa feita, mesmo tendo falhado


# =============================================================================
# 4. safety-declaration.json -- 10 chaves EXATAS, todas False.
# =============================================================================

def test_safety_declaration_has_exactly_10_keys_all_false(tmp_path):
    target = _confirmed_target_node()
    application = _application_with_target(target)
    config = _base_ladder_probe_config()

    probe_mod.probe_ladder_surface(application, config, str(tmp_path))

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

    result = probe_mod.probe_ladder_surface(application, config, str(tmp_path))

    assert result["aborted"] is True
    declaration = json.loads((tmp_path / "safety-declaration.json").read_text(encoding="utf-8"))
    assert all(value is False for value in declaration.values())


# =============================================================================
# 5. Nenhum '.text' de implementacao e lido, em nenhum caminho (feliz ou
#    abortado) -- prova direta via a propria instrumentacao do dublê.
# =============================================================================

def test_never_reads_dot_text_on_happy_path(tmp_path):
    target = _confirmed_target_node()
    application = _application_with_target(target)
    config = _base_ladder_probe_config()

    probe_mod.probe_ladder_surface(application, config, str(tmp_path))

    assert target.text_accessed is False


def test_never_reads_dot_text_on_identity_mismatch(tmp_path):
    target = FakeNode(name="ERRADO", type_guid="errado", object_guid="errado", is_folder=False)
    application = _application_with_target(target)
    config = _base_ladder_probe_config()

    probe_mod.probe_ladder_surface(application, config, str(tmp_path))

    assert target.text_accessed is False


# =============================================================================
# 6. Artefatos obrigatorios sempre presentes (feliz e abortado) +
#    checksums.sha256 gravado por ultimo.
# =============================================================================

REQUIRED_ARTIFACTS = (
    "manifest.json", "target-identity.json", "runtime-types.json", "interfaces.json",
    "properties.json", "methods.json", "safe-getter-results.json",
    "candidate-representation-members.json", "diagnostics.json",
    "safety-declaration.json", "checksums.sha256", "report.md",
)


def test_all_required_artifacts_exist_on_happy_path(tmp_path):
    target = _confirmed_target_node()
    application = _application_with_target(target)
    config = _base_ladder_probe_config()

    probe_mod.probe_ladder_surface(application, config, str(tmp_path))

    for filename in REQUIRED_ARTIFACTS:
        assert (tmp_path / filename).is_file(), "artefato ausente: %s" % filename


def test_all_required_artifacts_exist_on_abort(tmp_path):
    target = FakeNode(name="ERRADO", type_guid="errado", object_guid="errado", is_folder=False)
    application = _application_with_target(target)
    config = _base_ladder_probe_config()

    probe_mod.probe_ladder_surface(application, config, str(tmp_path))

    for filename in REQUIRED_ARTIFACTS:
        assert (tmp_path / filename).is_file(), "artefato ausente: %s" % filename


def test_checksums_cover_manifest_and_candidates(tmp_path):
    target = _confirmed_target_node()
    application = _application_with_target(target)
    config = _base_ladder_probe_config()

    probe_mod.probe_ladder_surface(application, config, str(tmp_path))

    checksums_text = (tmp_path / "checksums.sha256").read_text(encoding="utf-8")
    assert "manifest.json" in checksums_text
    assert "candidate-representation-members.json" in checksums_text
    assert "safety-declaration.json" in checksums_text


# =============================================================================
# 7. Configuracao invalida do proprio ladder_probe_config (defesa em
#    profundidade do probe -- a validacao "de verdade" e run_config.py).
# =============================================================================

def test_missing_required_config_field_aborts_without_navigating(tmp_path):
    application = _application_with_target(_confirmed_target_node())
    config = _base_ladder_probe_config()
    del config["expected_guid"]

    result = probe_mod.probe_ladder_surface(application, config, str(tmp_path))

    assert result["aborted"] is True
    assert result["abort_reason"] == "ladder_probe_config_invalid"


def test_empty_string_config_field_aborts(tmp_path):
    application = _application_with_target(_confirmed_target_node())
    config = _base_ladder_probe_config()
    config["expected_name"] = ""

    result = probe_mod.probe_ladder_surface(application, config, str(tmp_path))

    assert result["aborted"] is True
    assert result["abort_reason"] == "ladder_probe_config_invalid"


def test_probe_never_raises_even_with_completely_malformed_config(tmp_path):
    application = _application_with_target(_confirmed_target_node())
    result = probe_mod.probe_ladder_surface(application, "not-a-dict", str(tmp_path))
    assert result["aborted"] is True
    assert result["abort_reason"] == "ladder_probe_config_invalid"

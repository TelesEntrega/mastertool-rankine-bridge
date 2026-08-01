"""Testa scripts/mastertool/probes/17_probe_ladder_dynamic_surface.py EM
ISOLAMENTO (lado IronPython 2.7, roda DENTRO do MasterTool) -- Fase L1
(docs/14-ladder-roadmap.md), IRMAO de test_probe_16_ladder_surface.py.

Mesma filosofia de dubles (fakes) que o teste do probe 16: nenhum proxy CLR
real, so o suficiente para exercitar navegacao bounded/indexada + identidade
+ enumeracao dir() + reflexao CLR + portoes de controle + getters seguros.

Carregamento do modulo: o arquivo comeca com digito ('17_...'), entao
'import probes.17_probe...' e SyntaxError -- e preciso carregar pelo
CAMINHO. Ao contrario do teste do probe 16, este arquivo NAO reusa
`automation.supervised_snapshot_runner._load_ladder_probe_module` porque
aquele carregador esta fixado no CAMINHO do probe 16 (fora de escopo desta
fatia alterar o runner) -- o mesmo mecanismo de carregamento (tentar
`importlib.util`, cair para `imp` so em IronPython 2.7) e reproduzido aqui,
localmente, apontando para o probe 17.
"""

import json
import os
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_MASTERTOOL = REPO_ROOT / "scripts" / "mastertool"
PROBE_PATH = SCRIPTS_MASTERTOOL / "probes" / "17_probe_ladder_dynamic_surface.py"

if str(SCRIPTS_MASTERTOOL) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_MASTERTOOL))


def _load_probe_module():
    module_name = "mastertool_bridge_probe_17_ladder_dynamic_surface"
    try:
        import importlib.util as _importlib_util
    except ImportError:
        _importlib_util = None

    if _importlib_util is not None and hasattr(_importlib_util, "spec_from_file_location"):
        spec = _importlib_util.spec_from_file_location(module_name, str(PROBE_PATH))
        if spec is None or spec.loader is None:
            raise ImportError("nao foi possivel montar o spec do probe 17: %s" % PROBE_PATH)
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
    def __init__(self, properties=None, methods=None):
        self._properties = properties or []
        self._methods = methods or []

    def GetProperties(self):
        return self._properties

    def GetMethods(self):
        return self._methods


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


TARGET_NAME = "FB_PISCA_EXEMPLO"
TARGET_GUID = "00000000-0000-0000-0000-000000000002"
TARGET_TYPE_GUID = "6f9dac99-8de1-4efc-8465-68ac443b7d08"


class FakeNode(object):
    """Proxy CLR minimo. `dir_names` controla exatamente o que
    `capabilities.diagnostic_dir()` enxerga via dir() -- via `__dir__`
    customizado (nunca `__getattr__`, que dir() nao consulta). `clr_type` e
    o que `GetType().GetProperties()/GetMethods()` enxergam -- os dois
    conjuntos sao deliberadamente independentes, para simular exatamente o
    cenario do achado real (membro visto por dir(), nao visto por
    reflexao)."""

    def __init__(self, name, type_guid, object_guid, is_folder, children=None, clr_type=None,
                extra_properties=None, dir_names=None):
        self._name = name
        self._type_guid = type_guid
        self._object_guid = object_guid
        self._is_folder = is_folder
        self._children = children or []
        self._clr_type = clr_type
        self._extra_properties = extra_properties or {}
        self._dir_names = dir_names or []
        self.text_accessed = False
        self.textual_declaration_accessed = False
        self.textual_implementation_accessed = False

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

    def __dir__(self):
        return list(self._dir_names)

    @property
    def text(self):
        # Nunca deveria ser acessado por este probe (proibido: leitura de
        # '.text' de implementacao/declaracao).
        self.text_accessed = True
        return "NUNCA DEVERIA SER LIDO"

    def __getattr__(self, name):
        if name == "textual_declaration":
            self.textual_declaration_accessed = True
        if name == "textual_implementation":
            self.textual_implementation_accessed = True
        if name in self._extra_properties:
            value = self._extra_properties[name]
            if isinstance(value, Exception):
                raise value
            return value
        raise AttributeError(name)


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


def _clr_type_no_textual_declaration():
    """Reflexao CLR do alvo NUNCA inclui 'textual_declaration' -- o achado
    real que motivou este probe. Inclui 'Networks' (safe getter whitelisted)
    e 'ConnectorCache' (bate EVIDENCE_TERMS mas fora da whitelist) so para
    o clr-members.json ter conteudo comparavel."""
    properties = [
        FakePropertyInfo("Networks", "Vendor.Ladder.Impl", "System.Int32"),
        FakePropertyInfo("ConnectorCache", "Vendor.Ladder.Impl", "System.IntPtr"),
    ]
    methods = [
        FakeMethodInfo("ExportNetwork", "Vendor.Ladder.Impl", "System.Void",
                       parameters=[FakeParameterInfo("path", "System.String")]),
    ]
    return FakeClrType(properties=properties, methods=methods)


def _confirmed_target_node(dir_names, extra_properties=None, clr_type=None):
    clr_type = clr_type if clr_type is not None else _clr_type_no_textual_declaration()
    props = {"Networks": 3}
    if extra_properties:
        props.update(extra_properties)
    return FakeNode(
        name=TARGET_NAME, type_guid=TARGET_TYPE_GUID, object_guid=TARGET_GUID,
        is_folder=False, clr_type=clr_type, extra_properties=props, dir_names=dir_names)


# =============================================================================
# 1. Controle presente -> dynamic_probe_validated=true (os dois caminhos:
#    via dir() e via hasattr() controlado gated).
# =============================================================================

def test_control_member_seen_via_dir_validates_probe(tmp_path):
    target = _confirmed_target_node(
        dir_names=["textual_declaration", "has_textual_declaration", "Networks"],
        extra_properties={"has_textual_declaration": True, "textual_declaration": object()})
    application = _application_with_target(target)
    config = _base_ladder_probe_config()

    result = probe_mod.probe_ladder_dynamic_surface(application, config, str(tmp_path))

    assert result["aborted"] is False
    assert result["dynamic_probe_validated"] is True
    assert result["result_case"] in ("A", "B")
    assert result["status"] == "ok"

    control = json.loads((tmp_path / "control-validation.json").read_text(encoding="utf-8"))
    assert control == {
        "control_member": "textual_declaration",
        "seen_by_dynamic_surface": True,
        "seen_by_clr_reflection": False,
        "dynamic_probe_validated": True,
    }
    # visto via dir(): hasattr() controlado NAO deveria ter sido necessario.
    assert target.textual_declaration_accessed is False


def test_control_member_seen_via_gated_hasattr_validates_probe(tmp_path):
    """'textual_declaration' AUSENTE do dir() (cenario tipico real -- dir()
    vazio para ExtendedObject[T]), mas 'has_textual_declaration' confirmado
    True libera o hasattr() controlado, que confirma presenca."""
    target = _confirmed_target_node(
        dir_names=["has_textual_declaration", "Networks"],
        extra_properties={"has_textual_declaration": True, "textual_declaration": object()})
    application = _application_with_target(target)
    config = _base_ladder_probe_config()

    result = probe_mod.probe_ladder_dynamic_surface(application, config, str(tmp_path))

    assert result["dynamic_probe_validated"] is True
    control = json.loads((tmp_path / "control-validation.json").read_text(encoding="utf-8"))
    assert control["seen_by_dynamic_surface"] is True
    assert control["seen_by_clr_reflection"] is False
    # Desta vez o hasattr() controlado FOI necessario (gate aberto).
    assert target.textual_declaration_accessed is True
    whitelist_results = json.loads(
        (tmp_path / "whitelist-hasattr-results.json").read_text(encoding="utf-8"))
    entry = next(r for r in whitelist_results if r["name"] == "textual_declaration")
    assert entry["gate"] == "has_textual_declaration_confirmed_true"
    assert entry["hasattr_result"] is True


# =============================================================================
# 2. Controle ausente -> inconclusive, e NENHUMA conclusao sobre Ladder no
#    report.
# =============================================================================

def test_control_member_absent_is_inconclusive_and_report_bars_conclusions(tmp_path):
    target = _confirmed_target_node(
        dir_names=["Networks"],
        extra_properties={"has_textual_declaration": False, "has_textual_implementation": False})
    application = _application_with_target(target)
    config = _base_ladder_probe_config()

    result = probe_mod.probe_ladder_dynamic_surface(application, config, str(tmp_path))

    assert result["aborted"] is False
    assert result["dynamic_probe_validated"] is False
    assert result["result_case"] == "C"
    assert result["status"] == "inconclusive"

    control = json.loads((tmp_path / "control-validation.json").read_text(encoding="utf-8"))
    assert control["dynamic_probe_validated"] is False
    assert control["seen_by_dynamic_surface"] is False

    # o portao nao foi confirmado True -- hasattr() controlado NUNCA tentado.
    assert target.textual_declaration_accessed is False

    report_text = (tmp_path / "report.md").read_text(encoding="utf-8")
    assert "INCONCLUSIVO" in report_text
    assert "NENHUMA conclusao sobre a existencia ou ausencia de uma API Ladder" in report_text


def test_control_member_absent_because_hasattr_fails_even_with_gate_open(tmp_path):
    """Gate 'has_textual_declaration' confirmado True, mas o hasattr()
    controlado sobre 'textual_declaration' falha mesmo assim (ex.: extensao
    anexada de forma inconsistente) -- ainda assim inconclusive, nao um
    falso positivo."""
    target = _confirmed_target_node(
        dir_names=["has_textual_declaration", "Networks"],
        extra_properties={"has_textual_declaration": True})  # textual_declaration OMITIDO -> AttributeError
    application = _application_with_target(target)
    config = _base_ladder_probe_config()

    result = probe_mod.probe_ladder_dynamic_surface(application, config, str(tmp_path))

    assert result["dynamic_probe_validated"] is False
    assert result["result_case"] == "C"
    assert target.textual_declaration_accessed is True  # tentativa foi feita (gate aberto)


# =============================================================================
# 3. Membro proibido NUNCA e invocado -- teste explicito por termo proibido.
# =============================================================================

def test_forbidden_term_member_never_invoked_even_if_seen_in_dir(tmp_path):
    """'ExportXml' aparece no dir() e bate EVIDENCE_TERMS ('export'/'xml'),
    mas contem termo proibido ('export') -- vira candidato, NUNCA invocado,
    e nao pode aparecer em safe-getter-results.json de jeito nenhum (nem
    esta na SAFE_GETTER_WHITELIST)."""
    target = _confirmed_target_node(
        dir_names=["ExportXml", "has_textual_declaration", "Networks"],
        extra_properties={
            "has_textual_declaration": True, "textual_declaration": object(),
            "ExportXml": RuntimeError("NUNCA deveria ser chamado"),
        })
    application = _application_with_target(target)
    config = _base_ladder_probe_config()

    probe_mod.probe_ladder_dynamic_surface(application, config, str(tmp_path))

    dynamic_dir_members = json.loads(
        (tmp_path / "dynamic-dir-members.json").read_text(encoding="utf-8"))
    export_entry = next(m for m in dynamic_dir_members if m["name"] == "ExportXml")
    assert export_entry["invoked"] is False
    assert export_entry["hasattr_checked"] is False

    safe_getter_results = json.loads(
        (tmp_path / "safe-getter-results.json").read_text(encoding="utf-8"))
    assert "ExportXml" not in [r["member"] for r in safe_getter_results]


def test_every_safe_getter_whitelist_name_free_of_forbidden_terms():
    """Prova estatica: nenhum nome em SAFE_GETTER_WHITELIST contem qualquer
    termo de FORBIDDEN_GETTER_NAME_TERMS -- defesa em profundidade
    documentada no proprio modulo."""
    for name in probe_mod.SAFE_GETTER_WHITELIST:
        lowered = name.lower()
        for term in probe_mod.FORBIDDEN_GETTER_NAME_TERMS:
            assert term not in lowered, "%s contem termo proibido %s" % (name, term)


# =============================================================================
# 4. Metodo com parametros nunca e invocado.
# =============================================================================

def test_method_with_parameters_never_invoked_even_if_whitelisted_by_name(tmp_path):
    """'Networks' aparece tanto como property segura (invocavel) QUANTO
    (hipoteticamente) poderia ter uma variante metodo -- este probe so
    conhece nomes via whitelist plana (sem metadados de assinatura vindos de
    dir()), entao a garantia real e: SOMENTE SAFE_GETTER_WHITELIST e os 4
    controles sao tocados; um metodo de reflexao com parametros
    ('ExportNetwork') nunca aparece em safe-getter-results.json nem em
    whitelist-hasattr-results.json."""
    clr_type = FakeClrType(
        properties=[FakePropertyInfo("Networks", "Vendor.Ladder.Impl", "System.Int32")],
        methods=[FakeMethodInfo("ExportNetwork", "Vendor.Ladder.Impl", "System.Void",
                                parameters=[FakeParameterInfo("path", "System.String")])])
    target = _confirmed_target_node(
        dir_names=["Networks", "ExportNetwork", "has_textual_declaration"],
        extra_properties={"has_textual_declaration": False},
        clr_type=clr_type)
    application = _application_with_target(target)
    config = _base_ladder_probe_config()

    probe_mod.probe_ladder_dynamic_surface(application, config, str(tmp_path))

    safe_getter_results = json.loads(
        (tmp_path / "safe-getter-results.json").read_text(encoding="utf-8"))
    assert "ExportNetwork" not in [r["member"] for r in safe_getter_results]

    whitelist_results = json.loads(
        (tmp_path / "whitelist-hasattr-results.json").read_text(encoding="utf-8"))
    assert "ExportNetwork" not in [r["name"] for r in whitelist_results]


# =============================================================================
# 5. Divergencia de identidade aborta ANTES de sondar qualquer coisa.
# =============================================================================

def test_identity_mismatch_aborts_before_probing_dynamic_surface(tmp_path):
    target = FakeNode(
        name="NOME_ERRADO", type_guid=TARGET_TYPE_GUID, object_guid=TARGET_GUID, is_folder=False,
        clr_type=None, dir_names=["textual_declaration"],
        extra_properties={"textual_declaration": object()})
    application = _application_with_target(target)
    config = _base_ladder_probe_config()

    result = probe_mod.probe_ladder_dynamic_surface(application, config, str(tmp_path))

    assert result["aborted"] is True
    assert result["abort_reason"] == "target_identity_mismatch"
    assert result["target_identity_confirmed"] is False
    assert result["dynamic_probe_validated"] is False
    assert result["result_case"] == "C"

    # nenhum artefato de sondagem dinamica populado.
    dynamic_dir_members = json.loads(
        (tmp_path / "dynamic-dir-members.json").read_text(encoding="utf-8"))
    assert dynamic_dir_members == []
    control = json.loads((tmp_path / "control-validation.json").read_text(encoding="utf-8"))
    assert control == {
        "control_member": "textual_declaration",
        "seen_by_dynamic_surface": False,
        "seen_by_clr_reflection": False,
        "dynamic_probe_validated": False,
    }
    assert target.textual_declaration_accessed is False
    assert target.text_accessed is False


def test_never_reads_dot_text_on_happy_path(tmp_path):
    target = _confirmed_target_node(
        dir_names=["textual_declaration", "has_textual_declaration", "Networks"],
        extra_properties={"has_textual_declaration": True, "textual_declaration": object()})
    application = _application_with_target(target)
    config = _base_ladder_probe_config()

    probe_mod.probe_ladder_dynamic_surface(application, config, str(tmp_path))

    assert target.text_accessed is False


# =============================================================================
# 6. Delta dir() vs CLR calculado corretamente (dynamic_only / shared).
# =============================================================================

def test_dynamic_only_and_shared_delta_computed_correctly(tmp_path):
    """'Networks' esta em dir() E na reflexao CLR (shared); 'textual_declaration'
    esta em dir() mas NAO na reflexao CLR (dynamic_only); 'ConnectorCache'
    esta so na reflexao CLR (nunca aparece em nenhum dos dois arquivos de
    dir(), so em clr-members.json)."""
    target = _confirmed_target_node(
        dir_names=["Networks", "textual_declaration", "has_textual_declaration"],
        extra_properties={"has_textual_declaration": True, "textual_declaration": object()})
    application = _application_with_target(target)
    config = _base_ladder_probe_config()

    probe_mod.probe_ladder_dynamic_surface(application, config, str(tmp_path))

    dynamic_only = json.loads((tmp_path / "dynamic-only-members.json").read_text(encoding="utf-8"))
    shared = json.loads((tmp_path / "shared-members.json").read_text(encoding="utf-8"))
    clr_members = json.loads((tmp_path / "clr-members.json").read_text(encoding="utf-8"))

    dynamic_only_names = set(m["name"] for m in dynamic_only)
    shared_names = set(m["name"] for m in shared)
    clr_names = set(m["member"] for m in clr_members)

    assert "textual_declaration" in dynamic_only_names
    assert "has_textual_declaration" in dynamic_only_names
    assert "Networks" in shared_names
    assert "Networks" not in dynamic_only_names
    assert "textual_declaration" not in shared_names
    assert "ConnectorCache" in clr_names
    assert "ConnectorCache" not in dynamic_only_names and "ConnectorCache" not in shared_names

    # particao exata: todo membro visto em dir() esta em exatamente um dos
    # dois conjuntos.
    dir_member_names = dynamic_only_names | shared_names
    assert dir_member_names == {"Networks", "textual_declaration", "has_textual_declaration"}
    assert dynamic_only_names.isdisjoint(shared_names)


# =============================================================================
# 7. Candidatos classificados sem serem invocados.
# =============================================================================

def test_ladder_candidate_classified_but_never_invoked(tmp_path):
    """'NetworkBuffer' bate EVIDENCE_TERMS ('network') e nao esta na
    SAFE_GETTER_WHITELIST -- vira candidato, classification
    'candidate_ladder_representation', reason_not_invoked 'not previously
    approved', invoked=False, e NUNCA aparece em safe-getter-results.json."""
    target = _confirmed_target_node(
        dir_names=["NetworkBuffer", "has_textual_declaration"],
        extra_properties={
            "has_textual_declaration": False,
            "NetworkBuffer": RuntimeError("NUNCA deveria ser chamado"),
        })
    application = _application_with_target(target)
    config = _base_ladder_probe_config()

    result = probe_mod.probe_ladder_dynamic_surface(application, config, str(tmp_path))

    assert result["ladder_candidate_count"] == 1
    candidates = json.loads((tmp_path / "ladder-candidate-members.json").read_text(encoding="utf-8"))
    assert len(candidates) == 1
    candidate = candidates[0]
    assert candidate["name"] == "NetworkBuffer"
    assert candidate["classification"] == "candidate_ladder_representation"
    assert candidate["reason_not_invoked"] == "not previously approved"
    assert candidate["invoked"] is False
    assert candidate["hasattr_checked"] is False

    safe_getter_results = json.loads(
        (tmp_path / "safe-getter-results.json").read_text(encoding="utf-8"))
    assert "NetworkBuffer" not in [r["member"] for r in safe_getter_results]
    # Candidato inofensivo: nenhum termo proibido a anotar.
    assert candidate["forbidden_term"] is None


def test_side_effecting_candidate_is_marked_forbidden_not_merely_unapproved(tmp_path):
    """`export_xml` e candidato Ladder legitimo (bate 'export'/'xml') E
    escreve em disco. Ele NAO pode sair do artefato indistinguivel de
    `networks`: quem desenhar a fase 18 le este JSON, nao a whitelist do
    codigo, e "not previously approved" sugeriria que basta aprovar. O
    registro precisa carregar o termo proibido de forma legivel por maquina
    e uma razao que diga que a proibicao e desta fase."""
    target = _confirmed_target_node(
        dir_names=["export_xml", "networks", "has_textual_declaration"],
        extra_properties={
            "has_textual_declaration": False,
            "export_xml": RuntimeError("NUNCA deveria ser chamado"),
            "networks": RuntimeError("NUNCA deveria ser chamado"),
        })
    application = _application_with_target(target)

    result = probe_mod.probe_ladder_dynamic_surface(
        application, _base_ladder_probe_config(), str(tmp_path))

    candidates = json.loads(
        (tmp_path / "ladder-candidate-members.json").read_text(encoding="utf-8"))
    by_name = dict((c["name"], c) for c in candidates)

    exporter = by_name["export_xml"]
    assert exporter["forbidden_term"] == "export"
    assert "forbidden in this phase" in exporter["reason_not_invoked"]
    assert exporter["invoked"] is False

    # O candidato inofensivo continua distinguivel do proibido -- se os dois
    # convergissem, a anotacao nao estaria informando nada.
    benign = by_name["networks"]
    assert benign["forbidden_term"] is None
    assert benign["reason_not_invoked"] == "not previously approved"

    # Nenhum dos dois foi invocado -- ambos levantariam RuntimeError, entao
    # chegar ate aqui ja prova isso. A checagem explicita e sobre o artefato:
    # nem `export_xml` nem `networks` (minusculo, fora da whitelist) podem
    # aparecer em safe-getter-results.json. Note que a passada de whitelist
    # roda normalmente sobre os nomes APROVADOS -- o que se exige aqui nao e
    # ausencia de invocacao, e que a invocacao nunca alcance estes dois.
    probed = [r["member"] for r in json.loads(
        (tmp_path / "safe-getter-results.json").read_text(encoding="utf-8"))]
    assert "export_xml" not in probed
    assert "networks" not in probed


def test_uninteresting_dir_member_without_evidence_term_is_not_a_candidate(tmp_path):
    target = _confirmed_target_node(
        dir_names=["RandomInternalFlag", "has_textual_declaration"],
        extra_properties={"has_textual_declaration": False})
    application = _application_with_target(target)
    config = _base_ladder_probe_config()

    probe_mod.probe_ladder_dynamic_surface(application, config, str(tmp_path))

    dynamic_dir_members = json.loads(
        (tmp_path / "dynamic-dir-members.json").read_text(encoding="utf-8"))
    entry = next(m for m in dynamic_dir_members if m["name"] == "RandomInternalFlag")
    assert entry["classification"] == "unclassified"

    candidates = json.loads((tmp_path / "ladder-candidate-members.json").read_text(encoding="utf-8"))
    assert "RandomInternalFlag" not in [c["name"] for c in candidates]


# =============================================================================
# 8. Safe getter whitelist -- getters ja aprovados no probe 16 sao
#    invocados quando presentes; falha de um nao impede os demais.
# =============================================================================

def test_safe_getter_whitelist_invocation_and_failure_isolation(tmp_path):
    target = _confirmed_target_node(
        dir_names=["Networks", "NetworkCount", "has_textual_declaration"],
        extra_properties={
            "has_textual_declaration": False,
            "Networks": 3,
            "NetworkCount": RuntimeError("falha simulada de leitura"),
        })
    application = _application_with_target(target)
    config = _base_ladder_probe_config()

    probe_mod.probe_ladder_dynamic_surface(application, config, str(tmp_path))

    safe_getter_results = json.loads(
        (tmp_path / "safe-getter-results.json").read_text(encoding="utf-8"))
    by_member = {r["member"]: r for r in safe_getter_results}

    assert by_member["Networks"]["state"] == "confirmed"
    assert by_member["Networks"]["representation"]["value"] == 3
    assert by_member["NetworkCount"]["state"] == "unknown"


def test_safe_getter_not_present_reports_unsupported_state(tmp_path):
    """Um nome da whitelist ausente do proxy (getattr levanta AttributeError)
    ainda e sondado (whitelist e fixa, independente do dir()) mas o estado
    reflete a ausencia -- sem quebrar a execucao."""
    target = _confirmed_target_node(
        dir_names=["has_textual_declaration"],
        extra_properties={"has_textual_declaration": False})
    application = _application_with_target(target)
    config = _base_ladder_probe_config()

    probe_mod.probe_ladder_dynamic_surface(application, config, str(tmp_path))

    safe_getter_results = json.loads(
        (tmp_path / "safe-getter-results.json").read_text(encoding="utf-8"))
    by_member = {r["member"]: r for r in safe_getter_results}
    assert by_member["Name"]["state"] == "unsupported"


# =============================================================================
# 9. safety-declaration.json -- 10 chaves exatas, todas False.
# =============================================================================

def test_safety_declaration_has_exactly_10_keys_all_false(tmp_path):
    target = _confirmed_target_node(
        dir_names=["Networks"], extra_properties={"has_textual_declaration": False})
    application = _application_with_target(target)
    config = _base_ladder_probe_config()

    probe_mod.probe_ladder_dynamic_surface(application, config, str(tmp_path))

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

    result = probe_mod.probe_ladder_dynamic_surface(application, config, str(tmp_path))

    assert result["aborted"] is True
    declaration = json.loads((tmp_path / "safety-declaration.json").read_text(encoding="utf-8"))
    assert all(value is False for value in declaration.values())


# =============================================================================
# 10. Artefatos obrigatorios sempre presentes + checksums.sha256 por ultimo.
# =============================================================================

REQUIRED_ARTIFACTS = (
    "manifest.json", "target-identity.json", "clr-members.json",
    "dynamic-dir-members.json", "dynamic-only-members.json", "shared-members.json",
    "whitelist-hasattr-results.json", "safe-getter-results.json",
    "ladder-candidate-members.json", "control-validation.json", "diagnostics.json",
    "safety-declaration.json", "checksums.sha256", "report.md",
)


def test_all_required_artifacts_exist_on_happy_path(tmp_path):
    target = _confirmed_target_node(
        dir_names=["Networks", "has_textual_declaration"],
        extra_properties={"has_textual_declaration": False})
    application = _application_with_target(target)
    config = _base_ladder_probe_config()

    probe_mod.probe_ladder_dynamic_surface(application, config, str(tmp_path))

    for filename in REQUIRED_ARTIFACTS:
        assert (tmp_path / filename).is_file(), "artefato ausente: %s" % filename


def test_all_required_artifacts_exist_on_abort(tmp_path):
    target = FakeNode(name="ERRADO", type_guid="errado", object_guid="errado", is_folder=False)
    application = _application_with_target(target)
    config = _base_ladder_probe_config()

    probe_mod.probe_ladder_dynamic_surface(application, config, str(tmp_path))

    for filename in REQUIRED_ARTIFACTS:
        assert (tmp_path / filename).is_file(), "artefato ausente: %s" % filename


def test_checksums_cover_manifest_and_control_validation(tmp_path):
    target = _confirmed_target_node(
        dir_names=["Networks", "has_textual_declaration"],
        extra_properties={"has_textual_declaration": False})
    application = _application_with_target(target)
    config = _base_ladder_probe_config()

    probe_mod.probe_ladder_dynamic_surface(application, config, str(tmp_path))

    checksums_text = (tmp_path / "checksums.sha256").read_text(encoding="utf-8")
    assert "manifest.json" in checksums_text
    assert "control-validation.json" in checksums_text
    assert "safety-declaration.json" in checksums_text


# =============================================================================
# 11. Configuracao invalida do proprio ladder_probe_config (defesa em
#     profundidade, mesma regra do probe 16).
# =============================================================================

def test_missing_required_config_field_aborts_without_navigating(tmp_path):
    application = _application_with_target(
        _confirmed_target_node(dir_names=[], extra_properties={"has_textual_declaration": False}))
    config = _base_ladder_probe_config()
    del config["expected_guid"]

    result = probe_mod.probe_ladder_dynamic_surface(application, config, str(tmp_path))

    assert result["aborted"] is True
    assert result["abort_reason"] == "ladder_probe_config_invalid"


def test_probe_never_raises_even_with_completely_malformed_config(tmp_path):
    application = _application_with_target(
        _confirmed_target_node(dir_names=[], extra_properties={"has_textual_declaration": False}))
    result = probe_mod.probe_ladder_dynamic_surface(application, "not-a-dict", str(tmp_path))
    assert result["aborted"] is True
    assert result["abort_reason"] == "ladder_probe_config_invalid"


def test_invalid_target_node_id_aborts(tmp_path):
    application = _application_with_target(
        _confirmed_target_node(dir_names=[], extra_properties={"has_textual_declaration": False}))
    config = _base_ladder_probe_config(target_node_id="not-application/0/1")

    result = probe_mod.probe_ladder_dynamic_surface(application, config, str(tmp_path))

    assert result["aborted"] is True
    assert result["abort_reason"] == "invalid_target_node_id"


def test_navigation_index_out_of_range_aborts(tmp_path):
    application = _application_with_target(
        _confirmed_target_node(dir_names=[], extra_properties={"has_textual_declaration": False}))
    config = _base_ladder_probe_config(target_node_id="application/0/999")

    result = probe_mod.probe_ladder_dynamic_surface(application, config, str(tmp_path))

    assert result["aborted"] is True
    assert result["abort_reason"] == "navigation_failed"


# =============================================================================
# Taxonomia corrigida: ACESSO POR NOME vs ENUMERACAO DE NOMES.
#
# A primeira execucao real provou por que as duas nao podem compartilhar um
# gate: o controle foi confirmado por hasattr() (acesso funciona) enquanto
# dir() devolveu lista VAZIA (enumeracao nao funciona). Com gate unico isso
# virou "caso B -- evidencia forte de que a superficie dinamica nao expoe
# Ladder", conclusao que os dados nao sustentam: `ladder_candidate_count` e
# derivado da lista do dir(), entao zero candidatos vindos de zero nomes
# enumerados nao mede ausencia.
# =============================================================================


def _dynamic_probe(tmp_path, dir_names, extra_properties=None, clr_type=None):
    target = _confirmed_target_node(
        dir_names=dir_names,
        extra_properties=extra_properties or {"has_textual_declaration": True,
                                              "textual_declaration": object()},
        clr_type=clr_type)
    application = _application_with_target(target)
    return probe_mod.probe_ladder_dynamic_surface(
        application, _base_ladder_probe_config(), str(tmp_path))


def test_case_A_enumeration_with_candidate(tmp_path):
    result = _dynamic_probe(
        tmp_path, ["NetworkBuffer", "has_textual_declaration", "textual_declaration"])
    assert result["result_case"] == "A"
    assert result["dynamic_named_access_validated"] is True
    assert result["dynamic_enumeration_available"] is True
    assert result["candidate_search_exhaustive"] is True
    assert result["ladder_candidate_count"] > 0
    assert result["status"] == "ok"


def test_case_B_enumeration_without_candidate(tmp_path):
    """Enumeracao REAL (dir() com nomes) e nenhum candidato -- unico cenario
    em que zero candidatos significa alguma coisa."""
    result = _dynamic_probe(
        tmp_path, ["banana", "abacaxi", "has_textual_declaration", "textual_declaration"])
    assert result["result_case"] == "B"
    assert result["dynamic_enumeration_available"] is True
    assert result["candidate_search_exhaustive"] is True
    assert result["ladder_candidate_count"] == 0
    assert result["status"] == "ok"

    report = (tmp_path / "report.md").read_text(encoding="utf-8")
    # A conclusao precisa ser LIMITADA ao canal enumerado.
    assert "canal dinamico enumerado" in report
    assert "NAO afirma ausencia global" in report


def test_case_C_control_not_found_is_inconclusive(tmp_path):
    result = _dynamic_probe(
        tmp_path, ["banana"],
        extra_properties={"has_textual_declaration": False})
    assert result["result_case"] == "C"
    assert result["dynamic_named_access_validated"] is False
    assert result["status"] == "inconclusive"


def test_case_D_control_found_but_dir_is_empty(tmp_path):
    """O cenario da execucao real de 2026-07-27."""
    result = _dynamic_probe(tmp_path, [])
    assert result["result_case"] == "D"
    assert result["dynamic_named_access_validated"] is True
    assert result["dynamic_enumeration_available"] is False
    assert result["candidate_search_exhaustive"] is False
    assert result["status"] == "dynamic_discovery_channel_unavailable"


class _DirRaisesNode(FakeNode):
    """Proxy cujo dir() LEVANTA -- subclasse, nunca monkeypatch da FakeNode:
    substituir `__dir__` na classe compartilhada vaza para todos os outros
    testes do arquivo."""

    def __dir__(self):
        raise RuntimeError("proxy DLR sem introspeccao generica")


class _DirNonEnumerableNode(FakeNode):
    """Proxy cujo dir() devolve algo nao iteravel."""

    def __dir__(self):
        return 42


def _node_of(cls):
    return cls(
        name=TARGET_NAME, type_guid=TARGET_TYPE_GUID, object_guid=TARGET_GUID,
        is_folder=False, clr_type=_clr_type_no_textual_declaration(),
        extra_properties={"Networks": 3, "has_textual_declaration": True,
                          "textual_declaration": object()},
        dir_names=[])


def test_case_D_when_dir_raises(tmp_path):
    application = _application_with_target(_node_of(_DirRaisesNode))
    result = probe_mod.probe_ladder_dynamic_surface(
        application, _base_ladder_probe_config(), str(tmp_path))

    assert result["result_case"] == "D"
    assert result["dynamic_enumeration_available"] is False


def test_case_D_when_dir_returns_non_enumerable(tmp_path):
    application = _application_with_target(_node_of(_DirNonEnumerableNode))
    result = probe_mod.probe_ladder_dynamic_surface(
        application, _base_ladder_probe_config(), str(tmp_path))

    assert result["result_case"] == "D"
    assert result["dynamic_enumeration_available"] is False


def test_zero_candidates_with_zero_enumerated_is_never_case_B(tmp_path):
    """A assercao central da correcao. Antes dela, este exato cenario
    produzia 'caso B: evidencia forte' -- afirmando ausencia a partir de uma
    enumeracao que nunca aconteceu."""
    result = _dynamic_probe(tmp_path, [])

    assert result["ladder_candidate_count"] == 0
    assert result["dynamic_dir_member_count"] == 0
    assert result["result_case"] != "B", (
        "zero candidatos + zero membros enumerados NAO e evidencia de ausencia")
    assert result["result_case"] == "D"

    report = (tmp_path / "report.md").read_text(encoding="utf-8")
    assert "Nenhuma conclusao pode ser feita" in report
    assert "NAO mede ausencia" in report


def test_manifest_exposes_the_two_capabilities_separately(tmp_path):
    result = _dynamic_probe(tmp_path, [])
    manifest = json.loads((tmp_path / "manifest.json").read_text(encoding="utf-8"))

    assert manifest["dynamic_named_access_validated"] is True
    assert manifest["dynamic_enumeration_available"] is False
    assert manifest["candidate_search_exhaustive"] is False
    assert manifest["result_case"] == "D"
    assert result["ladder_candidate_count"] == 0

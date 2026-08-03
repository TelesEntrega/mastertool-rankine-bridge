"""Testa scripts/mastertool/automation/ (runner supervisionado interno --
lado IronPython 2.7, roda DENTRO do MasterTool). Contrato:
docs/16-supervised-runner-contract.md.

Estes modulos sao escritos para IronPython 2.7, mas precisam ser
IMPORTAVEIS e testaveis em Python 3.11 (a suite e py3) -- ver
tests/unit/test_validate_command_line_execution.py para o padrao ja
aprovado de testar um script IronPython a partir do py3 com dublês
(fakes) no lugar de 'projects'/'system'/objetos do ScriptEngine.

Cobertura minima exigida pelo contrato (slice etapa-b-runner-interno):
  - run_config: build:true reprova; chave desconhecida em operations
    reprova; schema_version errado reprova; falta de campo obrigatorio
    (ex.: expected_application_guid) reprova; save/online/download/force
    reprovam via common/safety.py.
  - run_status: estado invalido levanta excecao; status-history.jsonl
    recebe uma linha por transicao e nunca e truncado.
  - main(): aborta quando script_globals nao tem 'projects'; aborta quando
    project.path diverge do esperado; aborta quando ha mismatch de
    identidade da Application.

Como a suite roda em CPython 3.11 (nao IronPython/CLI), a checagem real de
procedencia (_check_provenance) sempre reprovaria PRIMEIRO -- o que
impediria testar qualquer passo posterior da sequencia de 14 passos. Por
isso _check_provenance() e uma funcao isolada e testavel: um teste dedicado
prova o comportamento REAL dela (reprova fora de IronPython 2.7, sem
monkeypatch nenhum); os demais testes de main() fazem monkeypatch dela para
"True" e assim exercitam os passos seguintes com dublês.
"""

import json
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_MASTERTOOL = REPO_ROOT / "scripts" / "mastertool"

if str(SCRIPTS_MASTERTOOL) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_MASTERTOOL))

from automation import run_config, run_status, supervised_snapshot_runner  # noqa: E402
from common import safety  # noqa: E402


# =============================================================================
# Helpers / fakes
# =============================================================================

def _base_config(run_dir, **overrides):
    output_dir = str(run_dir / "output")
    config = {
        "schema_version": 1,
        "run_id": run_dir.name,
        "mode": "supervised_snapshot",
        "repo_root": str(REPO_ROOT),
        "mastertool_scripts_dir": str(SCRIPTS_MASTERTOOL),
        "expected_project_path": "C:\\projetos\\Copia.project",
        "expected_project_sha256": "deadbeef" * 8,
        "expected_application_name": "Application",
        "expected_application_guid": "00000000-0000-0000-0000-000000000001",
        "expected_application_type_guid": "639b491f-5557-464c-af91-1471bac9f549",
        "run_dir": str(run_dir),
        "output_dir": output_dir,
        "allowed_output_root": str(run_dir.parent),
        "operations": {
            "scan_project_tree": False,
            "export_text": False,
            "inventory_graphic_objects": False,
            "build": False,
            "save": False,
            "online": False,
        },
    }
    config.update(overrides)
    return config


def _write_config(run_dir, config):
    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / "run-config.json").write_text(json.dumps(config), encoding="utf-8")


class _FakeInterface(object):
    def __init__(self, name):
        self.Name = name


class _FakeCollectionType(object):
    def GetInterfaces(self):
        return [_FakeInterface("ICollection`1")]


class FakeEmptyChildrenCollection(object):
    """Colecao vazia (Count=0), o suficiente para o exportador confirmar
    ICollection/IList sem precisar indexar nada."""

    @property
    def Count(self):
        return 0

    def GetType(self):
        return _FakeCollectionType()

    def __getitem__(self, index):
        raise IndexError("colecao vazia")


class FakeApplication(object):
    """So o suficiente para _probe_application_identity() (get_name(False)/
    type/guid) e, quando `with_empty_children=True`, para um export() real
    de uma Application SEM filhos (get_children(False) -> colecao vazia)."""

    def __init__(self, name="Application",
                type_guid="639b491f-5557-464c-af91-1471bac9f549",
                object_guid="00000000-0000-0000-0000-000000000001",
                with_empty_children=False):
        self._name = name
        self._type_guid = type_guid
        self._object_guid = object_guid
        self._with_empty_children = with_empty_children

    def get_name(self, recursive):
        return self._name

    @property
    def type(self):
        return self._type_guid

    @property
    def guid(self):
        return self._object_guid

    def get_children(self, recursive):
        if not self._with_empty_children:
            raise AssertionError(
                "get_children() nao deveria ser chamado neste teste "
                "(FakeApplication criada sem with_empty_children=True).")
        return FakeEmptyChildrenCollection()


class FakeProject(object):
    def __init__(self, path, application=None):
        self.path = path
        self.active_application = application if application is not None else FakeApplication()


class FakeProjects(object):
    def __init__(self, primary):
        self.primary = primary


# =============================================================================
# run_config.py
# =============================================================================

def test_load_run_config_accepts_valid_minimal_config(tmp_path):
    config = _base_config(tmp_path)
    _write_config(tmp_path, config)
    loaded = run_config.load_run_config(str(tmp_path))
    assert loaded["schema_version"] == 1
    assert loaded["operations"]["scan_project_tree"] is False


def test_load_run_config_rejects_wrong_schema_version(tmp_path):
    config = _base_config(tmp_path, schema_version=2)
    _write_config(tmp_path, config)
    with pytest.raises(run_config.RunConfigError, match="schema_version"):
        run_config.load_run_config(str(tmp_path))


def test_load_run_config_rejects_missing_required_field(tmp_path):
    config = _base_config(tmp_path)
    del config["expected_application_guid"]
    _write_config(tmp_path, config)
    with pytest.raises(run_config.RunConfigError, match="expected_application_guid"):
        run_config.load_run_config(str(tmp_path))


def test_load_run_config_rejects_unknown_operation_key(tmp_path):
    config = _base_config(tmp_path)
    config["operations"]["teleport_robot"] = True
    _write_config(tmp_path, config)
    with pytest.raises(run_config.RunConfigError, match="teleport_robot"):
        run_config.load_run_config(str(tmp_path))


def test_load_run_config_rejects_build_true(tmp_path):
    config = _base_config(tmp_path)
    config["operations"]["build"] = True
    _write_config(tmp_path, config)
    with pytest.raises(run_config.RunConfigError, match="build"):
        run_config.load_run_config(str(tmp_path))


@pytest.mark.parametrize("op_key", ["save", "online", "download", "force"])
def test_load_run_config_rejects_forbidden_operations_via_safety(tmp_path, op_key):
    config = _base_config(tmp_path)
    config["operations"][op_key] = True
    _write_config(tmp_path, config)
    with pytest.raises(run_config.RunConfigError, match=op_key):
        run_config.load_run_config(str(tmp_path))


def test_load_run_config_permitted_operations_still_pass(tmp_path):
    config = _base_config(tmp_path)
    config["operations"]["scan_project_tree"] = True
    config["operations"]["export_text"] = True
    config["operations"]["inventory_graphic_objects"] = True
    _write_config(tmp_path, config)
    loaded = run_config.load_run_config(str(tmp_path))
    assert loaded["operations"]["export_text"] is True


def test_load_run_config_missing_file_raises(tmp_path):
    with pytest.raises(run_config.RunConfigError):
        run_config.load_run_config(str(tmp_path))


def test_load_run_config_malformed_json_raises(tmp_path):
    tmp_path.mkdir(parents=True, exist_ok=True)
    (tmp_path / "run-config.json").write_text("{not valid json", encoding="utf-8")
    with pytest.raises(run_config.RunConfigError):
        run_config.load_run_config(str(tmp_path))


def test_operation_safety_map_matches_safety_module_semantics():
    """Prova que o mapeamento reutiliza common/safety.py de verdade (nao uma
    segunda lista paralela): cada operacao mapeada deve estar em uma das
    listas de bloqueio permanente/fase de common/safety.py."""
    for safety_name in run_config.OPERATION_SAFETY_MAP.values():
        with pytest.raises(safety.SafetyError):
            safety.assert_operation_allowed(safety_name)


# =============================================================================
# run_config.py -- secao 'ladder_probe' (Fase L1, contrato secao 3.1). Testa
# SOMENTE a validacao/configuracao da operacao 'probe_ladder_surface' --
# nunca o comportamento do probe em si (isso e
# tests/unit/test_probe_16_ladder_surface.py) nem a integracao runner->probe
# (isso e a secao 'runner integration -- probe_ladder_surface' mais abaixo
# neste mesmo arquivo). As tres coisas ficam deliberadamente separadas.
# =============================================================================

def _valid_ladder_probe_section():
    return {
        "target_node_id": "application/9/4",
        "expected_name": "BLINK_QUE_FUNCIONA",
        "expected_guid": "beca53e2-8466-404a-baf5-9fba1adc0fac",
        "expected_type_guid": "6f9dac99-8de1-4efc-8465-68ac443b7d08",
    }


def test_load_run_config_accepts_probe_ladder_surface_with_valid_ladder_probe_section(tmp_path):
    config = _base_config(tmp_path)
    config["operations"]["probe_ladder_surface"] = True
    config["ladder_probe"] = _valid_ladder_probe_section()
    _write_config(tmp_path, config)

    loaded = run_config.load_run_config(str(tmp_path))

    assert loaded["operations"]["probe_ladder_surface"] is True
    assert loaded["ladder_probe"] == _valid_ladder_probe_section()


def test_load_run_config_rejects_probe_ladder_surface_true_without_ladder_probe_section(tmp_path):
    config = _base_config(tmp_path)
    config["operations"]["probe_ladder_surface"] = True
    _write_config(tmp_path, config)

    with pytest.raises(run_config.RunConfigError, match="ladder_probe"):
        run_config.load_run_config(str(tmp_path))


def test_load_run_config_rejects_ladder_probe_section_when_operation_is_off(tmp_path):
    """Config incoerente NAO e aceito por omissao: a secao presente com a
    operacao desligada tambem reprova (mesmo criterio fail-closed em ambas
    as direcoes)."""
    config = _base_config(tmp_path)
    assert config["operations"].get("probe_ladder_surface", False) is False
    config["ladder_probe"] = _valid_ladder_probe_section()
    _write_config(tmp_path, config)

    with pytest.raises(run_config.RunConfigError, match="ladder_probe"):
        run_config.load_run_config(str(tmp_path))


@pytest.mark.parametrize("missing_field", [
    "target_node_id", "expected_name", "expected_guid", "expected_type_guid",
])
def test_load_run_config_rejects_ladder_probe_missing_required_field(tmp_path, missing_field):
    config = _base_config(tmp_path)
    config["operations"]["probe_ladder_surface"] = True
    section = _valid_ladder_probe_section()
    del section[missing_field]
    config["ladder_probe"] = section
    _write_config(tmp_path, config)

    with pytest.raises(run_config.RunConfigError, match=missing_field):
        run_config.load_run_config(str(tmp_path))


@pytest.mark.parametrize("empty_field", [
    "target_node_id", "expected_name", "expected_guid", "expected_type_guid",
])
def test_load_run_config_rejects_ladder_probe_empty_string_field(tmp_path, empty_field):
    config = _base_config(tmp_path)
    config["operations"]["probe_ladder_surface"] = True
    section = _valid_ladder_probe_section()
    section[empty_field] = ""
    config["ladder_probe"] = section
    _write_config(tmp_path, config)

    with pytest.raises(run_config.RunConfigError, match=empty_field):
        run_config.load_run_config(str(tmp_path))


def test_load_run_config_rejects_ladder_probe_section_not_an_object(tmp_path):
    config = _base_config(tmp_path)
    config["operations"]["probe_ladder_surface"] = True
    config["ladder_probe"] = "not-an-object"
    _write_config(tmp_path, config)

    with pytest.raises(run_config.RunConfigError, match="ladder_probe"):
        run_config.load_run_config(str(tmp_path))


def test_probe_ladder_surface_is_a_known_operation_key(tmp_path):
    assert "probe_ladder_surface" in run_config.KNOWN_OPERATION_KEYS


# =============================================================================
# run_config.py -- secao 'limits' (achado do revisor, 2026-07-24: limites de
# travessia nao podiam continuar caindo nos defaults, mais frouxos, das
# classes em common/ -- ver supervised_snapshot_runner.py)
# =============================================================================

def test_default_limits_locked_against_accidental_change():
    """Trava os valores default esperados (os JA VALIDADOS pelos probes
    12/13/14 contra a baseline v0.1.0) -- uma mudanca acidental futura em
    DEFAULT_LIMITS deve FALHAR este teste, nunca passar silenciosamente."""
    assert run_config.DEFAULT_LIMITS == {
        "scanner": {
            "max_depth": 8,
            "max_total_nodes": 2000,
            "max_children_per_node": 128,
            "expected_root_count": None,
        },
        "exporter": {
            "max_depth": 8,
            "max_total_nodes": 1000,
            "max_children_per_node": 128,
            "max_text_objects": 300,
            "max_document_characters": 1000000,
            "max_total_characters": 15000000,
        },
        "inventory": {
            "max_depth": 8,
            "max_total_nodes": 1000,
            "max_children_per_node": 128,
        },
    }


def test_load_run_config_applies_default_limits_when_limits_section_absent(tmp_path):
    config = _base_config(tmp_path)
    assert "limits" not in config
    _write_config(tmp_path, config)
    loaded = run_config.load_run_config(str(tmp_path))
    assert loaded["limits"] == run_config.DEFAULT_LIMITS


def test_load_run_config_config_values_override_defaults_per_key(tmp_path):
    config = _base_config(tmp_path)
    config["limits"] = {
        "scanner": {"max_total_nodes": 4000, "expected_root_count": 4},
        "exporter": {"max_text_objects": 900},
    }
    _write_config(tmp_path, config)
    loaded = run_config.load_run_config(str(tmp_path))

    # chaves informadas sao sobrepostas...
    assert loaded["limits"]["scanner"]["max_total_nodes"] == 4000
    assert loaded["limits"]["scanner"]["expected_root_count"] == 4
    assert loaded["limits"]["exporter"]["max_text_objects"] == 900
    # ...as NAO informadas (no mesmo bloco ou em blocos ausentes) continuam
    # no default.
    assert loaded["limits"]["scanner"]["max_depth"] == 8
    assert loaded["limits"]["scanner"]["max_children_per_node"] == 128
    assert loaded["limits"]["exporter"]["max_total_nodes"] == 1000
    assert loaded["limits"]["inventory"] == run_config.DEFAULT_LIMITS["inventory"]


def test_load_run_config_rejects_unknown_top_level_limits_block(tmp_path):
    config = _base_config(tmp_path)
    config["limits"] = {"downloader": {"max_depth": 8}}
    _write_config(tmp_path, config)
    with pytest.raises(run_config.RunConfigError, match="downloader"):
        run_config.load_run_config(str(tmp_path))


def test_load_run_config_rejects_unknown_key_in_exporter_limits(tmp_path):
    config = _base_config(tmp_path)
    config["limits"] = {"exporter": {"max_alien_objects": 10}}
    _write_config(tmp_path, config)
    with pytest.raises(run_config.RunConfigError, match="max_alien_objects"):
        run_config.load_run_config(str(tmp_path))


@pytest.mark.parametrize("bad_value", [0, -1, -100])
def test_load_run_config_rejects_zero_or_negative_limit_values(tmp_path, bad_value):
    config = _base_config(tmp_path)
    config["limits"] = {"scanner": {"max_total_nodes": bad_value}}
    _write_config(tmp_path, config)
    with pytest.raises(run_config.RunConfigError, match="max_total_nodes"):
        run_config.load_run_config(str(tmp_path))


def test_load_run_config_rejects_zero_expected_root_count(tmp_path):
    config = _base_config(tmp_path)
    config["limits"] = {"scanner": {"expected_root_count": 0}}
    _write_config(tmp_path, config)
    with pytest.raises(run_config.RunConfigError, match="expected_root_count"):
        run_config.load_run_config(str(tmp_path))


def test_load_run_config_accepts_null_expected_root_count(tmp_path):
    config = _base_config(tmp_path)
    config["limits"] = {"scanner": {"expected_root_count": None}}
    _write_config(tmp_path, config)
    loaded = run_config.load_run_config(str(tmp_path))
    assert loaded["limits"]["scanner"]["expected_root_count"] is None


# =============================================================================
# run_status.py
# =============================================================================

def test_status_writer_rejects_unknown_state(tmp_path):
    writer = run_status.StatusWriter(str(tmp_path), "2026-07-24_10-00-00")
    with pytest.raises(run_status.StatusError):
        writer.set_state("not_a_real_state")


def test_status_writer_writes_status_json_with_expected_fields(tmp_path):
    writer = run_status.StatusWriter(str(tmp_path), "2026-07-24_10-00-00")
    writer.set_state("script_started", detail="iniciando")

    status_path = tmp_path / "status.json"
    data = json.loads(status_path.read_text(encoding="utf-8"))
    assert data["schema_version"] == 1
    assert data["run_id"] == "2026-07-24_10-00-00"
    assert data["state"] == "script_started"
    assert data["detail"] == "iniciando"
    assert data["error"] is None
    assert data["traceback"] is None
    assert "updated_at" in data


def test_status_history_gets_one_line_per_transition_and_is_never_truncated(tmp_path):
    writer = run_status.StatusWriter(str(tmp_path), "run-1")
    writer.set_state("script_started")
    writer.set_state("provenance_validated")
    writer.set_state("project_identity_validated")

    history_path = tmp_path / "status-history.jsonl"
    lines = history_path.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 3
    states = [json.loads(line)["state"] for line in lines]
    assert states == ["script_started", "provenance_validated", "project_identity_validated"]

    # status.json corrente reflete so a ULTIMA transicao...
    status_data = json.loads((tmp_path / "status.json").read_text(encoding="utf-8"))
    assert status_data["state"] == "project_identity_validated"

    # ...mas o historico continua com as 3 linhas anteriores intactas.
    lines_after = history_path.read_text(encoding="utf-8").splitlines()
    assert len(lines_after) == 3


def test_status_writer_failed_state_accepted_as_terminal(tmp_path):
    writer = run_status.StatusWriter(str(tmp_path), "run-1")
    record = writer.set_state("failed", error="boom", traceback_text="Traceback...")
    assert record["state"] == "failed"
    data = json.loads((tmp_path / "status.json").read_text(encoding="utf-8"))
    assert data["error"] == "boom"
    assert data["traceback"] == "Traceback..."


# =============================================================================
# supervised_snapshot_runner.main()
# =============================================================================

# Procedencia forjada para os testes que exercitam os passos SEGUINTES da
# sequencia. Devolve a MESMA forma da funcao real (ok, detail, runtime) --
# um duble com forma diferente esconderia justamente o defeito que fez toda
# execucao supervisionada real terminar 'failed': o host validava uma secao
# 'runtime' que o runner nunca emitia.
_FAKE_RUNTIME = {
    "platform": "cli",
    "runtime_family": "IronPython",
    "version_info": [2, 7, 12],
    "provenance_confirmed": True,
}


def _fake_provenance_ok():
    return (True, "forcado no teste", dict(_FAKE_RUNTIME))


def test_check_provenance_fails_for_real_under_cpython():
    """Sem nenhum monkeypatch: prova o comportamento REAL de
    _check_provenance() no ambiente de teste (CPython 3.11, nao IronPython
    2.7/CLI) -- deve reprovar."""
    ok, detail, runtime = supervised_snapshot_runner._check_provenance()
    assert ok is False
    assert "platform=" in detail


def test_main_aborts_when_script_globals_has_no_projects(monkeypatch, tmp_path):
    monkeypatch.setattr(supervised_snapshot_runner, "_check_provenance", _fake_provenance_ok)

    run_dir = tmp_path / "2026-07-24_10-00-00"
    config = _base_config(run_dir)
    _write_config(run_dir, config)

    result = supervised_snapshot_runner.main(str(run_dir), {})

    assert result["final_state"] == "failed"
    assert result["abort_reason"] == "primary_project_unavailable"

    status_data = json.loads((run_dir / "status.json").read_text(encoding="utf-8"))
    assert status_data["state"] == "failed"

    history_lines = (run_dir / "status-history.jsonl").read_text(encoding="utf-8").splitlines()
    states = [json.loads(line)["state"] for line in history_lines]
    assert states == ["script_started", "provenance_validated", "failed"]


def test_main_aborts_when_project_path_diverges_from_expected(monkeypatch, tmp_path):
    monkeypatch.setattr(supervised_snapshot_runner, "_check_provenance", _fake_provenance_ok)

    run_dir = tmp_path / "2026-07-24_10-00-00"
    config = _base_config(run_dir)
    _write_config(run_dir, config)

    fake_project = FakeProject(path="C:\\projetos\\OUTRO_PROJETO.project")
    script_globals = {"projects": FakeProjects(primary=fake_project)}

    result = supervised_snapshot_runner.main(str(run_dir), script_globals)

    assert result["final_state"] == "failed"
    assert result["abort_reason"] == "project_identity_mismatch"

    history_lines = (run_dir / "status-history.jsonl").read_text(encoding="utf-8").splitlines()
    states = [json.loads(line)["state"] for line in history_lines]
    assert states == ["script_started", "provenance_validated", "failed"]


def test_main_aborts_when_application_identity_mismatches(monkeypatch, tmp_path):
    monkeypatch.setattr(supervised_snapshot_runner, "_check_provenance", _fake_provenance_ok)

    run_dir = tmp_path / "2026-07-24_10-00-00"
    config = _base_config(run_dir)
    _write_config(run_dir, config)

    mismatched_application = FakeApplication(
        name="Application", type_guid="639b491f-5557-464c-af91-1471bac9f549",
        object_guid="00000000-0000-0000-0000-000000000000")  # guid diferente do esperado
    fake_project = FakeProject(
        path=config["expected_project_path"], application=mismatched_application)
    script_globals = {"projects": FakeProjects(primary=fake_project)}

    result = supervised_snapshot_runner.main(str(run_dir), script_globals)

    assert result["final_state"] == "failed"
    assert result["abort_reason"] == "application_identity_mismatch"
    assert result["detail"][0]["field"] == "object_guid"

    # nada foi executado depois: nenhum artefato de output foi criado.
    output_dir = run_dir / "output"
    assert not output_dir.exists() or list(output_dir.iterdir()) == []

    # identidade e checada ANTES de status=project_identity_validated ser
    # escrito (contrato, secao 6: passo 8 acontece antes do passo 9) -- a
    # ultima transicao registrada e diretamente para 'failed'.
    history_lines = (run_dir / "status-history.jsonl").read_text(encoding="utf-8").splitlines()
    states = [json.loads(line)["state"] for line in history_lines]
    assert states == ["script_started", "provenance_validated", "failed"]


def test_main_aborts_on_run_dir_mismatch(monkeypatch, tmp_path):
    monkeypatch.setattr(supervised_snapshot_runner, "_check_provenance", _fake_provenance_ok)

    run_dir = tmp_path / "2026-07-24_10-00-00"
    other_dir = tmp_path / "algum-outro-lugar"
    config = _base_config(run_dir)
    config["run_dir"] = str(other_dir)
    _write_config(run_dir, config)

    result = supervised_snapshot_runner.main(str(run_dir), {"projects": FakeProjects(primary=None)})

    assert result["final_state"] == "failed"
    assert result["abort_reason"] == "run_dir_mismatch"


def test_main_aborts_on_invalid_run_config(monkeypatch, tmp_path):
    monkeypatch.setattr(supervised_snapshot_runner, "_check_provenance", _fake_provenance_ok)

    run_dir = tmp_path / "2026-07-24_10-00-00"
    config = _base_config(run_dir)
    config["operations"]["build"] = True
    _write_config(run_dir, config)

    result = supervised_snapshot_runner.main(str(run_dir), {})

    assert result["final_state"] == "failed"
    assert result["abort_reason"] == "run_config_invalid"


def test_main_never_raises_on_unexpected_exception(monkeypatch, tmp_path):
    """Mesmo uma excecao totalmente nao prevista (aqui, dentro de
    project_access.get_primary_project) nunca escapa de main() -- vira
    status=failed com traceback, e um dict e retornado."""
    monkeypatch.setattr(supervised_snapshot_runner, "_check_provenance", _fake_provenance_ok)

    from common import project_access

    def _boom(script_globals):
        raise RuntimeError("falha totalmente inesperada")

    monkeypatch.setattr(project_access, "get_primary_project", _boom)

    run_dir = tmp_path / "2026-07-24_10-00-00"
    config = _base_config(run_dir)
    _write_config(run_dir, config)

    result = supervised_snapshot_runner.main(str(run_dir), {})

    assert result["final_state"] == "failed"
    assert result["abort_reason"] == "unexpected_exception"
    assert "traceback" in result
    assert "RuntimeError" in result["traceback"]


def test_main_writes_run_report_and_completes_when_no_operations_requested(monkeypatch, tmp_path):
    """Happy path minimo: identidade confirmada, nenhuma operacao pedida em
    'operations' (todas False) -> passa direto para validating/completed,
    grava run-report.json com a declaracao final do contrato (secao 7)."""
    monkeypatch.setattr(supervised_snapshot_runner, "_check_provenance", _fake_provenance_ok)

    run_dir = tmp_path / "2026-07-24_10-00-00"
    config = _base_config(run_dir)
    _write_config(run_dir, config)

    fake_project = FakeProject(path=config["expected_project_path"])
    script_globals = {"projects": FakeProjects(primary=fake_project)}

    result = supervised_snapshot_runner.main(str(run_dir), script_globals)

    assert result["final_state"] == "completed"
    assert result["run_report"] == {
        "project_saved": False,
        "build_called": False,
        "online_operation": False,
        "download_called": False,
        "force_called": False,
        "original_project_touched": False,
        "limits_used": run_config.DEFAULT_LIMITS,
        # A secao 'runtime' e o que o host consome para confirmar procedencia.
        # Sem ela, toda execucao supervisionada real terminava 'failed'.
        "runtime": dict(_FAKE_RUNTIME),
    }

    run_report_path = run_dir / "output" / "run-report.json"
    assert run_report_path.exists()
    written = json.loads(run_report_path.read_text(encoding="utf-8"))
    assert written == result["run_report"]

    history_lines = (run_dir / "status-history.jsonl").read_text(encoding="utf-8").splitlines()
    states = [json.loads(line)["state"] for line in history_lines]
    assert states == [
        "script_started", "provenance_validated", "project_identity_validated",
        "validating", "completed",
    ]


def test_main_passes_configured_limits_including_expected_root_count_to_scanner(monkeypatch, tmp_path):
    """Achado do revisor (2026-07-24): o runner nao pode mais instanciar o
    scanner sem limites explicitos, nem perder 'expected_root_count' quando
    o config o fornecer. Monkeypatch no proprio construtor para capturar os
    kwargs recebidos de verdade."""
    monkeypatch.setattr(supervised_snapshot_runner, "_check_provenance", _fake_provenance_ok)

    run_dir = tmp_path / "2026-07-24_10-00-00"
    config = _base_config(run_dir)
    config["operations"]["scan_project_tree"] = True
    config["limits"] = {
        "scanner": {"max_total_nodes": 3333, "max_children_per_node": 64, "expected_root_count": 4},
    }
    _write_config(run_dir, config)

    captured_kwargs = {}

    class _FakeScanner(object):
        def __init__(self, **kwargs):
            captured_kwargs.update(kwargs)

        def scan(self, project):
            return {"tree": {"node_id": "root"}, "errors": []}

    monkeypatch.setattr(supervised_snapshot_runner.scanner_mod, "ReadOnlyProjectScanner", _FakeScanner)

    fake_project = FakeProject(path=config["expected_project_path"])
    script_globals = {"projects": FakeProjects(primary=fake_project)}

    result = supervised_snapshot_runner.main(str(run_dir), script_globals)

    assert result["final_state"] == "completed"
    assert captured_kwargs == {
        "max_depth": 8,
        "max_total_nodes": 3333,
        "max_children_per_node": 64,
        "expected_root_count": 4,
    }
    assert result["run_report"]["limits_used"]["scanner"]["expected_root_count"] == 4


# =============================================================================
# Procedencia — regressao da PRIMEIRA EXECUCAO SUPERVISIONADA REAL
# (2026-07-24 21:00, run 2026-07-24_21-00-43).
#
# A versao anterior de _check_provenance exigia
#   sys.platform == "cli"  E  "IronPython" in sys.version
# e REPROVOU dentro do MT8500 3.63 real, com:
#   platform='cli', IronPython em sys.version=False, version_info[:2]=(2, 7)
#
# Neste host `sys.version` devolve um BANNER DO PRODUTO, sem a palavra
# "IronPython" — fato ja documentado desde probes/00_smoke_test.py. Por isso
# common/compatibility.is_ironpython() usa OU, nao E. O runner reimplementou
# a regra em vez de reusar o helper, e a copia divergiu para o lado que
# quebra.
# =============================================================================

import sys as _sys

from automation import run_status as _status_module
from automation import supervised_snapshot_runner as _runner

# Banner real observado neste host: nao contem "IronPython".
_BANNER_SEM_IRONPYTHON = "2.7.12 (ScriptEngine.plugin 3.5.17.0)"


class _FakeVersionInfo(tuple):
    pass


def _force_runtime(monkeypatch, platform, version_text, version_pair):
    monkeypatch.setattr(_runner.sys, "platform", platform, raising=False)
    monkeypatch.setattr(_runner.sys, "version", version_text, raising=False)
    monkeypatch.setattr(_runner.sys, "version_info",
                        _FakeVersionInfo(version_pair), raising=False)
    from common import compatibility
    monkeypatch.setattr(compatibility.sys, "platform", platform, raising=False)
    monkeypatch.setattr(compatibility.sys, "version", version_text, raising=False)


def test_provenance_accepts_real_mt8500_banner_without_the_word_ironpython(monkeypatch):
    """O caso EXATO que reprovou na primeira execucao real."""
    _force_runtime(monkeypatch, "cli", _BANNER_SEM_IRONPYTHON, (2, 7, 12, "final", 0))
    ok, detail, _runtime = _runner._check_provenance()
    assert ok is True, detail


def test_provenance_still_accepts_banner_that_does_mention_ironpython(monkeypatch):
    _force_runtime(monkeypatch, "cli", "2.7.12 (IronPython 2.7.12)", (2, 7, 12, "final", 0))
    ok, _detail, _runtime = _runner._check_provenance()
    assert ok is True


def test_provenance_rejects_cpython3_outside_mastertool(monkeypatch):
    _force_runtime(monkeypatch, "win32", "3.11.8 (main)", (3, 11, 8, "final", 0))
    ok, detail, _runtime = _runner._check_provenance()
    assert ok is False
    assert "win32" in detail


def test_provenance_rejects_right_platform_but_wrong_version(monkeypatch):
    _force_runtime(monkeypatch, "cli", _BANNER_SEM_IRONPYTHON, (3, 4, 0, "final", 0))
    ok, _detail, _runtime = _runner._check_provenance()
    assert ok is False


def test_provenance_rejects_python27_that_is_not_cli(monkeypatch):
    """2.7 sozinho nao basta: CPython 2.7 fora do MasterTool deve reprovar."""
    _force_runtime(monkeypatch, "win32", "2.7.18 (CPython)", (2, 7, 18, "final", 0))
    ok, _detail, _runtime = _runner._check_provenance()
    assert ok is False


def test_provenance_reports_observed_runtime_even_when_it_fails(monkeypatch):
    """Valores OBSERVADOS preservados na reprovacao: o host precisa
    distinguir "rodou em CPython 3 fora do MasterTool" de "campo ausente".
    Sem isso as duas situacoes viram o mesmo `null`."""
    _force_runtime(monkeypatch, "win32", "3.11.8 (main)", (3, 11, 8, "final", 0))
    ok, _detail, runtime = _runner._check_provenance()

    assert ok is False
    assert runtime["platform"] == "win32"
    assert runtime["runtime_family"] == "CPython"
    assert runtime["version_info"] == [3, 11, 8]
    assert runtime["provenance_confirmed"] is False


def test_provenance_runtime_has_the_three_keys_the_host_consumes(monkeypatch):
    """O host (cli_probe_verify.check_provenance) le exatamente estas chaves
    sob 'runtime'. Este teste trava o contrato entre os dois lados -- foi a
    ausencia dele que deixou toda execucao supervisionada real terminar
    'failed' por um motivo sem relacao com a aquisicao."""
    _force_runtime(monkeypatch, "cli", _BANNER_SEM_IRONPYTHON, (2, 7, 12, "final", 0))
    _ok, _detail, runtime = _runner._check_provenance()

    from mastertool_bridge.automation.cli_probe_verify import check_provenance
    verdict = check_provenance({"runtime": runtime})

    assert verdict["inside_mastertool"] is True
    assert runtime["platform"] == "cli"
    assert runtime["runtime_family"] == "IronPython"
    assert list(runtime["version_info"][:2]) == [2, 7]


def test_run_report_carries_the_runtime_section():
    runtime = {"platform": "cli", "runtime_family": "IronPython",
               "version_info": [2, 7, 12], "provenance_confirmed": True}
    report = _runner._build_run_report({"scanner": {}}, runtime)

    assert report["runtime"] == runtime
    # Os 6 campos da declaracao do contrato continuam intactos.
    for key in ("project_saved", "build_called", "online_operation",
                "download_called", "force_called", "original_project_touched"):
        assert report[key] is False


def test_run_report_without_runtime_emits_empty_not_missing():
    """Campo ausente NAO pode virar sucesso: o host precisa ver a secao
    vazia e reprovar, em vez de nao encontrar a chave."""
    report = _runner._build_run_report({"scanner": {}})
    assert report["runtime"] == {}

    from mastertool_bridge.automation.cli_probe_verify import check_provenance
    assert check_provenance(report)["inside_mastertool"] is False


# =============================================================================
# Costura export -> indexador (achado do revisor, 2026-07-24, primeira
# execucao supervisionada REAL): build_static_index/load_export (lado host,
# src/mastertool_bridge/indexer/export_loader.py) exige manifest.json,
# flat-objects.json, text-index.json e checksums.sha256 em output/ -- os
# 2 primeiros nao eram gravados pelo runner. Os testes abaixo travam essa
# costura: os 4 arquivos existem apos export_text=True, flat-objects.json
# tem uma entrada por no achatado, manifest.json carrega os limites usados,
# e checksums.sha256 cobre os 2 arquivos novos (prova indireta, mas
# definitiva, de que a ORDEM de escrita esta correta: se manifest.json/
# flat-objects.json fossem gravados DEPOIS de checksums.sha256, eles
# simplesmente nao apareceriam no arquivo de checksums).
# =============================================================================

def _run_main_with_export_text(monkeypatch, tmp_path, application=None):
    monkeypatch.setattr(supervised_snapshot_runner, "_check_provenance", _fake_provenance_ok)

    run_dir = tmp_path / "2026-07-24_10-00-00"
    config = _base_config(run_dir)
    config["operations"]["export_text"] = True
    _write_config(run_dir, config)

    fake_application = application if application is not None else FakeApplication(with_empty_children=True)
    fake_project = FakeProject(path=config["expected_project_path"], application=fake_application)
    script_globals = {"projects": FakeProjects(primary=fake_project)}

    result = supervised_snapshot_runner.main(str(run_dir), script_globals)
    return run_dir, result


def test_main_export_text_writes_all_4_files_required_by_indexer(monkeypatch, tmp_path):
    run_dir, result = _run_main_with_export_text(monkeypatch, tmp_path)
    assert result["final_state"] == "completed", result

    output_dir = run_dir / "output"
    for filename in ("manifest.json", "flat-objects.json", "text-index.json", "checksums.sha256"):
        assert (output_dir / filename).is_file(), (
            "arquivo exigido por export_loader.REQUIRED_FILES ausente: %s" % filename)


def test_main_export_text_flat_objects_has_one_entry_per_flattened_object(monkeypatch, tmp_path):
    run_dir, result = _run_main_with_export_text(monkeypatch, tmp_path)
    assert result["final_state"] == "completed", result

    output_dir = run_dir / "output"
    flat_objects = json.loads((output_dir / "flat-objects.json").read_text(encoding="utf-8"))
    application_tree = json.loads((output_dir / "application-tree.json").read_text(encoding="utf-8"))

    from common import read_only_text_exporter as exporter_mod
    expected_flat = exporter_mod.flatten_tree(application_tree)

    assert isinstance(flat_objects, list)
    assert len(flat_objects) == len(expected_flat)
    # Application sem filhos -> exatamente 1 no achatado (a propria raiz).
    assert len(flat_objects) == 1
    assert flat_objects[0]["node_id"] == "application"


def test_main_export_text_manifest_has_expected_keys_and_limits_used(monkeypatch, tmp_path):
    run_dir, result = _run_main_with_export_text(monkeypatch, tmp_path)
    assert result["final_state"] == "completed", result

    manifest = json.loads((run_dir / "output" / "manifest.json").read_text(encoding="utf-8"))

    for key in ("schema_version", "script", "generated_at", "mode", "run_id",
               "exporter_config", "limits_used"):
        assert key in manifest, "campo ausente em manifest.json: %s" % key

    assert manifest["mode"] == "read_only"
    assert "supervised_snapshot_runner.py" in manifest["script"]
    assert manifest["limits_used"] == run_config.DEFAULT_LIMITS
    assert manifest["exporter_config"]["expected_application_guid"] == \
        "00000000-0000-0000-0000-000000000001"


def test_main_export_text_checksums_cover_manifest_and_flat_objects(monkeypatch, tmp_path):
    """Prova de ORDEM: manifest.json e flat-objects.json tem que ser
    gravados ANTES de checksums.sha256 -- se a ordem regredisse, estas 2
    entradas simplesmente sumiriam do arquivo de checksums (o
    write_checksums_file so cobre o que ja existe em disco no momento em
    que roda)."""
    run_dir, result = _run_main_with_export_text(monkeypatch, tmp_path)
    assert result["final_state"] == "completed", result

    checksums_text = (run_dir / "output" / "checksums.sha256").read_text(encoding="utf-8")
    assert "manifest.json" in checksums_text
    assert "flat-objects.json" in checksums_text
    assert "text-index.json" in checksums_text
    assert "application-tree.json" in checksums_text


# =============================================================================
# Visibilidade na aba "Mensagens de script" do MasterTool.
#
# ACHADO REAL da execucao 2026-07-24_21-21-01: o runner nao tinha NENHUM
# print(), diferente de todos os probes. Com a UI visivel -- cujo unico
# proposito e supervisao humana -- o operador viu a aba de Mensagens VAZIA e
# concluiu, corretamente, que o script nao havia rodado. O estado estava certo
# no disco; quem supervisiona olha a tela, nao o disco.
#
# Estes testes existem tambem porque a primeira tentativa de correcao usou
# `safety.read_only_banner()` sem `safety` estar importado no modulo. Como o
# print fica dentro de `try/except Exception: pass` (para nunca derrubar a
# aquisicao), o NameError seria ENGOLIDO EM SILENCIO e o banner simplesmente
# nao apareceria -- o mesmo tipo de falha invisivel que o achado original.
# =============================================================================


def test_status_writer_mirrors_every_transition_to_stdout(tmp_path, capsys):
    writer = _status_module.StatusWriter(str(tmp_path), "run-x")
    writer.set_state("script_started", detail="comecou")
    writer.set_state("failed", detail="parou", error="motivo_x")

    out = capsys.readouterr().out
    assert "SCRIPT_STARTED" in out
    assert "comecou" in out
    assert "FAILED" in out
    assert "motivo_x" in out


def test_runner_module_has_safety_imported_for_the_banner():
    """Regressao direta: o banner referencia `safety.read_only_banner()`.

    Sem o import, o `try/except` em volta do print engole o NameError e o
    banner desaparece sem deixar rastro."""
    assert hasattr(_runner, "safety")
    assert callable(_runner.safety.read_only_banner)


def test_banner_text_is_actually_produced_without_raising():
    texto = _runner.safety.read_only_banner()
    assert "SOMENTE LEITURA" in texto.upper()


# =============================================================================
# Fase L1, probe 17 -- lado INTERNO (run_config + run_status).
#
# Mesma regra fail-closed do probe 16 sobre uma secao propria. O que estes
# testes travam nao e a presenca da operacao, e a INDEPENDENCIA das duas:
# reutilizar a flag/secao do 16 tornaria impossivel rodar so uma das
# sondagens -- e comparar os dois metodos e justamente o objetivo da fase.
# =============================================================================

_DYNAMIC_TARGET = {
    "target_node_id": "application/9/4",
    "expected_name": "ALVO",
    "expected_guid": "guid-1",
    "expected_type_guid": "guid-2",
}


def _dynamic_ops(**extra):
    ops = {
        "scan_project_tree": False,
        "export_text": False,
        "inventory_graphic_objects": False,
        "build": False,
        "save": False,
        "online": False,
    }
    ops.update(extra)
    return ops


def test_run_config_accepts_dynamic_probe_operation(tmp_path):
    config = _base_config(
        tmp_path,
        operations=_dynamic_ops(probe_ladder_dynamic_surface=True),
        ladder_dynamic_probe=dict(_DYNAMIC_TARGET))
    _write_config(tmp_path, config)

    loaded = run_config.load_run_config(str(tmp_path))

    assert loaded["operations"]["probe_ladder_dynamic_surface"] is True
    assert loaded["ladder_dynamic_probe"] == _DYNAMIC_TARGET
    # Scanner/exportador desligados permanecem desligados.
    assert loaded["operations"]["scan_project_tree"] is False
    assert loaded["operations"]["export_text"] is False


def test_run_config_rejects_dynamic_operation_without_section(tmp_path):
    config = _base_config(
        tmp_path, operations=_dynamic_ops(probe_ladder_dynamic_surface=True))
    _write_config(tmp_path, config)

    with pytest.raises(run_config.RunConfigError, match="ladder_dynamic_probe"):
        run_config.load_run_config(str(tmp_path))


def test_run_config_rejects_dynamic_section_without_operation(tmp_path):
    """Fail-closed na direcao inversa tambem: secao presente com a operacao
    desligada e config incoerente, nao 'secao ignorada'."""
    config = _base_config(
        tmp_path,
        operations=_dynamic_ops(probe_ladder_dynamic_surface=False),
        ladder_dynamic_probe=dict(_DYNAMIC_TARGET))
    _write_config(tmp_path, config)

    with pytest.raises(run_config.RunConfigError, match="ladder_dynamic_probe"):
        run_config.load_run_config(str(tmp_path))


def test_run_config_rejects_dynamic_target_with_empty_field(tmp_path):
    for field in ("target_node_id", "expected_name", "expected_guid",
                  "expected_type_guid"):
        target = dict(_DYNAMIC_TARGET)
        target[field] = ""
        config = _base_config(
            tmp_path,
            operations=_dynamic_ops(probe_ladder_dynamic_surface=True),
            ladder_dynamic_probe=target)
        _write_config(tmp_path, config)

        with pytest.raises(run_config.RunConfigError, match=field):
            run_config.load_run_config(str(tmp_path))


def test_run_config_rejects_dynamic_target_with_missing_field(tmp_path):
    for field in ("target_node_id", "expected_name", "expected_guid",
                  "expected_type_guid"):
        target = dict(_DYNAMIC_TARGET)
        del target[field]
        config = _base_config(
            tmp_path,
            operations=_dynamic_ops(probe_ladder_dynamic_surface=True),
            ladder_dynamic_probe=target)
        _write_config(tmp_path, config)

        with pytest.raises(run_config.RunConfigError, match=field):
            run_config.load_run_config(str(tmp_path))


def test_run_config_still_rejects_unknown_operation_key(tmp_path):
    """A operacao nova nao pode ter afrouxado a guarda de chave desconhecida."""
    config = _base_config(
        tmp_path, operations=_dynamic_ops(probe_ladder_inventado=True))
    _write_config(tmp_path, config)

    with pytest.raises(run_config.RunConfigError, match="probe_ladder_inventado"):
        run_config.load_run_config(str(tmp_path))


def test_the_two_ladder_probes_are_independent(tmp_path):
    """Ligar o 17 nao liga o 16, e cada um exige a SUA secao."""
    config = _base_config(
        tmp_path,
        operations=_dynamic_ops(probe_ladder_dynamic_surface=True),
        ladder_dynamic_probe=dict(_DYNAMIC_TARGET))
    _write_config(tmp_path, config)

    loaded = run_config.load_run_config(str(tmp_path))

    assert loaded["operations"].get("probe_ladder_surface", False) is False
    assert "ladder_probe" not in loaded


def test_dynamic_probe_state_is_valid_and_not_terminal():
    """O estado dedicado existe (o probe 17 tem gate de validade proprio, ao
    contrario do 16 que reusou 'scanning') e NAO e terminal -- a execucao
    continua para 'validating'/'completed' depois dele."""
    assert "probing_ladder_dynamic_surface" in run_status.VALID_STATES
    assert "probing_ladder_dynamic_surface" not in run_status.TERMINAL_STATES


# =============================================================================
# Fase L1, probe 18 (canal Extender) -- lado INTERNO.
# =============================================================================

def test_run_config_accepts_extender_probe_operation(tmp_path):
    config = _base_config(
        tmp_path,
        operations=_dynamic_ops(probe_ladder_extender_surface=True),
        ladder_extender_probe=dict(_DYNAMIC_TARGET))
    _write_config(tmp_path, config)

    loaded = run_config.load_run_config(str(tmp_path))

    assert loaded["operations"]["probe_ladder_extender_surface"] is True
    assert loaded["ladder_extender_probe"] == _DYNAMIC_TARGET


def test_run_config_rejects_extender_operation_without_section(tmp_path):
    config = _base_config(
        tmp_path, operations=_dynamic_ops(probe_ladder_extender_surface=True))
    _write_config(tmp_path, config)

    with pytest.raises(run_config.RunConfigError, match="ladder_extender_probe"):
        run_config.load_run_config(str(tmp_path))


def test_run_config_rejects_extender_section_without_operation(tmp_path):
    config = _base_config(
        tmp_path,
        operations=_dynamic_ops(probe_ladder_extender_surface=False),
        ladder_extender_probe=dict(_DYNAMIC_TARGET))
    _write_config(tmp_path, config)

    with pytest.raises(run_config.RunConfigError, match="ladder_extender_probe"):
        run_config.load_run_config(str(tmp_path))


def test_run_config_rejects_extender_target_with_empty_field(tmp_path):
    for field in ("target_node_id", "expected_name", "expected_guid",
                  "expected_type_guid"):
        target = dict(_DYNAMIC_TARGET)
        target[field] = ""
        config = _base_config(
            tmp_path,
            operations=_dynamic_ops(probe_ladder_extender_surface=True),
            ladder_extender_probe=target)
        _write_config(tmp_path, config)

        with pytest.raises(run_config.RunConfigError, match=field):
            run_config.load_run_config(str(tmp_path))


def test_extender_probe_state_is_valid_and_not_terminal():
    assert "probing_ladder_extender_surface" in run_status.VALID_STATES
    assert "probing_ladder_extender_surface" not in run_status.TERMINAL_STATES


def test_the_three_ladder_states_are_distinct():
    """Cada estado marca uma fronteira operacional real -- um estado
    generico exigiria consultar campos auxiliares para saber onde a execucao
    parou."""
    states = ("scanning", "probing_ladder_dynamic_surface",
              "probing_ladder_extender_surface")
    assert len(set(states)) == 3
    for state in states:
        assert state in run_status.VALID_STATES


# --- exclusao mutua dos tres probes -----------------------------------------

def test_two_ladder_probes_in_the_same_run_are_refused(tmp_path):
    """Canais distintos, gates proprios: dois vereditos sob um unico status
    seria ambiguidade justamente no registro de auditoria."""
    config = _base_config(
        tmp_path,
        operations=_dynamic_ops(probe_ladder_surface=True,
                                probe_ladder_dynamic_surface=True),
        ladder_probe=dict(_DYNAMIC_TARGET),
        ladder_dynamic_probe=dict(_DYNAMIC_TARGET))
    _write_config(tmp_path, config)

    with pytest.raises(run_config.RunConfigError, match="Mais de um probe Ladder"):
        run_config.load_run_config(str(tmp_path))


def test_all_three_ladder_probes_together_are_refused(tmp_path):
    config = _base_config(
        tmp_path,
        operations=_dynamic_ops(probe_ladder_surface=True,
                                probe_ladder_dynamic_surface=True,
                                probe_ladder_extender_surface=True),
        ladder_probe=dict(_DYNAMIC_TARGET),
        ladder_dynamic_probe=dict(_DYNAMIC_TARGET),
        ladder_extender_probe=dict(_DYNAMIC_TARGET))
    _write_config(tmp_path, config)

    with pytest.raises(run_config.RunConfigError, match="Mais de um probe Ladder"):
        run_config.load_run_config(str(tmp_path))


def test_exactly_one_ladder_probe_is_accepted(tmp_path):
    """A exclusao mutua nao pode ter proibido o caso normal."""
    for op_key, section in (
            ("probe_ladder_surface", "ladder_probe"),
            ("probe_ladder_dynamic_surface", "ladder_dynamic_probe"),
            ("probe_ladder_extender_surface", "ladder_extender_probe")):
        config = _base_config(
            tmp_path,
            operations=_dynamic_ops(**{op_key: True}),
            **{section: dict(_DYNAMIC_TARGET)})
        _write_config(tmp_path, config)

        loaded = run_config.load_run_config(str(tmp_path))
        assert loaded["operations"][op_key] is True


# =============================================================================
# Fase L1, probe 19 (assinatura de export_xml) -- lado INTERNO.
# =============================================================================

_PLCOPEN_SECTION = "plcopen_export_signature_probe"


def _plcopen_target(**extra):
    target = dict(_DYNAMIC_TARGET)
    target.update(extra)
    return target


def test_run_config_accepts_plcopen_signature_operation(tmp_path):
    config = _base_config(
        tmp_path,
        operations=_dynamic_ops(probe_plcopen_export_signature=True),
        **{_PLCOPEN_SECTION: _plcopen_target()})
    _write_config(tmp_path, config)

    loaded = run_config.load_run_config(str(tmp_path))

    assert loaded["operations"]["probe_plcopen_export_signature"] is True
    assert loaded[_PLCOPEN_SECTION]["target_node_id"] == "application/9/4"


def test_run_config_rejects_plcopen_operation_without_section(tmp_path):
    config = _base_config(
        tmp_path, operations=_dynamic_ops(probe_plcopen_export_signature=True))
    _write_config(tmp_path, config)

    with pytest.raises(run_config.RunConfigError, match=_PLCOPEN_SECTION):
        run_config.load_run_config(str(tmp_path))


def test_run_config_rejects_plcopen_section_without_operation(tmp_path):
    config = _base_config(
        tmp_path,
        operations=_dynamic_ops(probe_plcopen_export_signature=False),
        **{_PLCOPEN_SECTION: _plcopen_target()})
    _write_config(tmp_path, config)

    with pytest.raises(run_config.RunConfigError, match=_PLCOPEN_SECTION):
        run_config.load_run_config(str(tmp_path))


def test_run_config_rejects_plcopen_incomplete_identity(tmp_path):
    for field in ("target_node_id", "expected_name", "expected_guid",
                  "expected_type_guid"):
        target = _plcopen_target()
        target[field] = ""
        config = _base_config(
            tmp_path,
            operations=_dynamic_ops(probe_plcopen_export_signature=True),
            **{_PLCOPEN_SECTION: target})
        _write_config(tmp_path, config)

        with pytest.raises(run_config.RunConfigError, match=field):
            run_config.load_run_config(str(tmp_path))


def test_inspect_active_application_defaults_to_true_when_absent(tmp_path):
    config = _base_config(
        tmp_path,
        operations=_dynamic_ops(probe_plcopen_export_signature=True),
        **{_PLCOPEN_SECTION: _plcopen_target()})
    _write_config(tmp_path, config)

    loaded = run_config.load_run_config(str(tmp_path))
    section = loaded[_PLCOPEN_SECTION]
    assert section.get("inspect_active_application", True) is True


def test_inspect_active_application_false_is_accepted_explicitly(tmp_path):
    config = _base_config(
        tmp_path,
        operations=_dynamic_ops(probe_plcopen_export_signature=True),
        **{_PLCOPEN_SECTION: _plcopen_target(inspect_active_application=False)})
    _write_config(tmp_path, config)

    loaded = run_config.load_run_config(str(tmp_path))
    assert loaded[_PLCOPEN_SECTION]["inspect_active_application"] is False


def test_inspect_active_application_rejects_non_boolean(tmp_path):
    """Booleano ESTRITO: 0/1/"true" fariam a config parecer valida com um
    valor que nao expressa a intencao."""
    for bad in (0, 1, "true", "false", None, []):
        config = _base_config(
            tmp_path,
            operations=_dynamic_ops(probe_plcopen_export_signature=True),
            **{_PLCOPEN_SECTION: _plcopen_target(inspect_active_application=bad)})
        _write_config(tmp_path, config)

        with pytest.raises(run_config.RunConfigError, match="inspect_active_application"):
            run_config.load_run_config(str(tmp_path))


def test_plcopen_signature_state_is_valid_and_not_terminal():
    assert "probing_plcopen_export_signature" in run_status.VALID_STATES
    assert "probing_plcopen_export_signature" not in run_status.TERMINAL_STATES


def test_plcopen_probe_is_mutually_exclusive_with_each_ladder_probe(tmp_path):
    """Combinacao com CADA um dos outros tres, uma a uma."""
    for other_op, other_section in (
            ("probe_ladder_surface", "ladder_probe"),
            ("probe_ladder_dynamic_surface", "ladder_dynamic_probe"),
            ("probe_ladder_extender_surface", "ladder_extender_probe")):
        config = _base_config(
            tmp_path,
            operations=_dynamic_ops(probe_plcopen_export_signature=True,
                                    **{other_op: True}),
            **{_PLCOPEN_SECTION: _plcopen_target(),
               other_section: dict(_DYNAMIC_TARGET)})
        _write_config(tmp_path, config)

        with pytest.raises(run_config.RunConfigError, match="Mais de um probe"):
            run_config.load_run_config(str(tmp_path))


# =============================================================================
# Fase L1, exportacao controlada -- lado INTERNO.
# =============================================================================

_EXPORT_SECTION = "plcopen_export"


def _export_section(**over):
    section = dict(_DYNAMIC_TARGET)
    section.update({
        "recursive": False,
        "export_folder_structure": False,
        "plain_text": False,
        "target_leaf_name": "pou-export",
    })
    section.update(over)
    return section


def test_run_config_accepts_export_operation(tmp_path):
    config = _base_config(
        tmp_path, operations=_dynamic_ops(export_plcopen_xml=True),
        **{_EXPORT_SECTION: _export_section()})
    _write_config(tmp_path, config)

    loaded = run_config.load_run_config(str(tmp_path))

    assert loaded["operations"]["export_plcopen_xml"] is True
    assert loaded[_EXPORT_SECTION]["target_leaf_name"] == "pou-export"


def test_run_config_rejects_export_without_section(tmp_path):
    config = _base_config(tmp_path, operations=_dynamic_ops(export_plcopen_xml=True))
    _write_config(tmp_path, config)
    with pytest.raises(run_config.RunConfigError, match=_EXPORT_SECTION):
        run_config.load_run_config(str(tmp_path))


def test_run_config_rejects_section_without_export_operation(tmp_path):
    config = _base_config(
        tmp_path, operations=_dynamic_ops(export_plcopen_xml=False),
        **{_EXPORT_SECTION: _export_section()})
    _write_config(tmp_path, config)
    with pytest.raises(run_config.RunConfigError, match=_EXPORT_SECTION):
        run_config.load_run_config(str(tmp_path))


def test_export_booleans_must_be_exactly_false(tmp_path):
    """Existem para AUDITORIA, nao para abrir matriz de execucao: uma
    combinacao nunca testada nao pode entrar por alguem editar o JSON."""
    for field in ("recursive", "export_folder_structure", "plain_text"):
        for bad in (True, 1, 0, "false", None):
            config = _base_config(
                tmp_path, operations=_dynamic_ops(export_plcopen_xml=True),
                **{_EXPORT_SECTION: _export_section(**{field: bad})})
            _write_config(tmp_path, config)
            with pytest.raises(run_config.RunConfigError, match=field):
                run_config.load_run_config(str(tmp_path))


def test_export_requires_target_leaf_name(tmp_path):
    section = _export_section()
    del section["target_leaf_name"]
    config = _base_config(
        tmp_path, operations=_dynamic_ops(export_plcopen_xml=True),
        **{_EXPORT_SECTION: section})
    _write_config(tmp_path, config)
    with pytest.raises(run_config.RunConfigError, match="target_leaf_name"):
        run_config.load_run_config(str(tmp_path))


def test_exporting_state_is_valid_and_not_terminal():
    assert "exporting_plcopen_xml" in run_status.VALID_STATES
    assert "exporting_plcopen_xml" not in run_status.TERMINAL_STATES


def test_export_is_mutually_exclusive_with_each_investigation_probe(tmp_path):
    for other_op, other_section in (
            ("probe_ladder_surface", "ladder_probe"),
            ("probe_ladder_dynamic_surface", "ladder_dynamic_probe"),
            ("probe_ladder_extender_surface", "ladder_extender_probe"),
            ("probe_plcopen_export_signature", "plcopen_export_signature_probe")):
        config = _base_config(
            tmp_path,
            operations=_dynamic_ops(export_plcopen_xml=True, **{other_op: True}),
            **{_EXPORT_SECTION: _export_section(),
               other_section: dict(_DYNAMIC_TARGET)})
        _write_config(tmp_path, config)
        with pytest.raises(run_config.RunConfigError, match="Mais de um probe"):
            run_config.load_run_config(str(tmp_path))


def test_runner_creates_export_root_only_after_output_dir_check(tmp_path, monkeypatch):
    """A guarda de output_dir vazio roda ANTES da criacao -- pre-criar
    qualquer coisa sob output/ abortava toda a execucao (run
    2026-07-28_11-37-05). O diretorio nasce vazio por construcao."""
    run_dir = tmp_path / "2026-07-28_12-00-00"
    output_dir = run_dir / "output"
    output_dir.mkdir(parents=True)
    # output_dir NAO vazio: a guarda deve reprovar e nada deve ser criado.
    (output_dir / "residuo.txt").write_text("de uma run anterior", encoding="utf-8")

    config = _base_config(
        run_dir, operations=_dynamic_ops(export_plcopen_xml=True),
        **{"plcopen_export": _export_section()})
    _write_config(run_dir, config)
    monkeypatch.setattr(supervised_snapshot_runner, "_check_provenance",
                        _fake_provenance_ok)

    result = supervised_snapshot_runner.main(str(run_dir), {})

    # A razao exata do abort depende de quao longe o ambiente dublado chega
    # (aqui reprova antes, em primary_project_unavailable). O que este teste
    # trava e a ORDEM: nenhuma guarda reprovada pode deixar diretorio criado
    # para tras.
    assert result["final_state"] == "failed"
    assert not (output_dir / "plcopen-export").exists(), (
        "nada pode ser criado quando uma guarda inicial reprova")


def test_output_dir_empty_guard_still_rejects_prefilled_output(tmp_path, monkeypatch):
    """A guarda NAO foi enfraquecida pela correcao -- continua reprovando
    output/ com residuo, que e a protecao contra sobrescrever run anterior."""
    run_dir = tmp_path / "2026-07-28_12-30-00"
    output_dir = run_dir / "output"
    output_dir.mkdir(parents=True)
    (output_dir / "residuo.txt").write_text("run anterior", encoding="utf-8")
    assert list(output_dir.iterdir()), "pre-condicao: output nao vazio"

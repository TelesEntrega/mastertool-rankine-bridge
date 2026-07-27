"""Testa scripts/mastertool/probes/15_validate_command_line_execution.py
(Etapa A do roadmap de automacao — docs/15-automation-launcher-roadmap.md):
prova minima e inofensiva de execucao via linha de comando do MasterTool.

Renomeado em 2026-07-24 (era tests/unit/test_probe_cli_invocation.py, testando
scripts/mastertool/automation/probe_cli_invocation.py) para acompanhar o
arquivo renomeado/movido para scripts/mastertool/probes/
15_validate_command_line_execution.py.

Carregamento: o arquivo real termina com uma chamada `main()` no escopo do
modulo (mesmo padrao de TODOS os scripts 00-15 existentes, ver
00_smoke_test.py e probes/14_inventory_graphic_pous.py) — nao ha guarda
`if __name__ == "__main__"` em nenhum script deste diretorio, entao nao
adicionamos uma aqui so para "facilitar teste": carregamos o arquivo real via
importlib.util (spec_from_file_location + exec_module), a mesma forma que o
MasterTool executaria via --runscript. Isso deixa a chamada de main() do
rodape do arquivo rodar uma vez de verdade (dry-run externo, sem 'projects'/
'system' no namespace) — provando que o arquivo roda de ponta a ponta sem
lancar excecao mesmo fora do MasterTool — e devolve um modulo REAL (nao um
dict solto como runpy.run_path devolveria) cujas funcoes fecham sobre os
proprios atributos do modulo. Isso importa: monkeypatch.setattr(modulo,
"nome", fake) SO afeta closures internas se o objeto monkeypatchado for o
mesmo dict de globals usado pelas funcoes — importlib garante isso,
runpy.run_path NAO (ele copia o resultado para um dict novo).

Cobre os MINIMOS pedidos pela tarefa: dry-run completo sem 'projects'/
'system' disponiveis; captura de argv vazio vs. com argumentos simulados; as
4 camadas de resolucao de diretorio de saida testadas isoladamente com fakes
simulando falha de escrita em cada camada; falha simulada em cada passo
individual (interpreter_info, cwd, script_file, env, globals, project)
confirmando que os demais passos e a gravacao final continuam acontecendo; e
o formato EXATO de saida pedido (schema_version==1 int, runtime.platform/
version/version_info, globals.projects_available/system_available bool,
project.primary_available/path, safety.project_modified/save_called/
build_called/online_operation).
"""

import importlib.util
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT_PATH = REPO_ROOT / "scripts" / "mastertool" / "probes" / "15_validate_command_line_execution.py"
SCRIPTS_MASTERTOOL = REPO_ROOT / "scripts" / "mastertool"

if str(SCRIPTS_MASTERTOOL) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_MASTERTOOL))


def _load_module(monkeypatch, tmp_path, argv=None):
    """Carrega o arquivo REAL como um modulo Python de verdade (via
    importlib), executando a chamada main() do rodape do arquivo uma vez
    (dry-run externo, sem 'projects'/'system' — prova que o arquivo roda de
    ponta a ponta fora do MasterTool sem lancar excecao). cwd e isolado em
    tmp_path para nunca escrever de verdade no repo durante os testes.
    Devolve o objeto modulo (nao um dict), para que
    monkeypatch.setattr(modulo, ...) afete de verdade as funcoes internas."""
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(sys, "argv", argv if argv is not None else [str(SCRIPT_PATH)])
    spec = importlib.util.spec_from_file_location(
        "validate_command_line_execution_under_test_%s" % id(tmp_path), str(SCRIPT_PATH))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)  # executa o arquivo inteiro, inclusive main() do rodape
    return mod


# =============================================================================
# 1. dry-run completo sem 'projects'/'system' disponiveis (fora do MasterTool)
# =============================================================================

def test_dry_run_without_projects_still_writes_report(monkeypatch, tmp_path):
    mod = _load_module(monkeypatch, tmp_path, argv=[str(SCRIPT_PATH)])

    # main() ja rodou uma vez ao carregar o modulo (rodape do arquivo). Roda
    # de novo, de forma controlada, com script_globals SEM 'projects'/
    # 'system' (simula execucao fora do MasterTool real).
    report = mod.main({})

    assert report["script_started"] is True
    assert report["schema_version"] == 1
    assert report["globals"]["projects_available"] is False
    assert report["globals"]["system_available"] is False
    assert report["project"]["primary_available"] is False
    assert report["project"]["path"] is None
    assert report["completed_at"] is not None
    assert report["safety"]["project_modified"] is False
    assert report["safety"]["save_called"] is False
    assert report["safety"]["build_called"] is False
    assert report["safety"]["online_operation"] is False
    assert report["safety_declaration"]["read_only"] is True
    assert report["safety_declaration"]["project_content_accessed"] is False

    # relatorio deve ter sido gravado em disco (alguma camada, ja que cwd
    # (tmp_path) e sempre gravavel no ambiente de teste).
    resolution = report["output_dir_resolution"]
    assert any(a["success"] for a in resolution), resolution


def test_dry_run_projects_present_but_primary_missing_is_unsupported(monkeypatch, tmp_path):
    mod = _load_module(monkeypatch, tmp_path, argv=[str(SCRIPT_PATH)])

    class ProjectsNoPrimary(object):
        pass  # getattr(obj, "primary") levanta AttributeError -> unsupported

    report = mod.main({"projects": ProjectsNoPrimary()})
    assert report["globals"]["projects_available"] is True
    assert report["project"]["primary_available"] is False
    assert report["project"]["path"] is None
    assert report["project_detail"]["primary_state"] == "unsupported"


def test_dry_run_primary_available_but_path_read_fails_is_isolated_failure(monkeypatch, tmp_path):
    mod = _load_module(monkeypatch, tmp_path, argv=[str(SCRIPT_PATH)])

    class ExplodingPath(object):
        @property
        def path(self):
            raise RuntimeError("falha simulada ao ler .path")

    class ProjectsWithPrimary(object):
        primary = ExplodingPath()

    report = mod.main({"projects": ProjectsWithPrimary()})
    # primary em si foi confirmado (getattr(projects, "primary") funcionou);
    # a falha isolada e em .path, que nao deve travar o restante.
    assert report["project"]["primary_available"] is True
    assert report["project"]["path"] is None
    assert report["completed_at"] is not None


def test_dry_run_projects_primary_confirmed_without_path_probe_touching_other_members(monkeypatch, tmp_path):
    mod = _load_module(monkeypatch, tmp_path, argv=[str(SCRIPT_PATH)])

    class ProjectsWithPrimary(object):
        primary = object()  # sem atributo 'path' -> getattr(primary, "path") falha

    report = mod.main({"projects": ProjectsWithPrimary()})
    assert report["globals"]["projects_available"] is True
    assert report["project"]["primary_available"] is True
    assert report["project"]["path"] is None
    # garante que so getattr foi usado -- nunca navegacao/leitura alem disso
    assert report["safety_declaration"]["project_navigation_attempted"] is False


def test_dry_run_full_happy_path_projects_system_primary_path_all_available(monkeypatch, tmp_path):
    mod = _load_module(monkeypatch, tmp_path, argv=[str(SCRIPT_PATH)])

    class PrimaryProject(object):
        path = "C:\\Projetos\\ProjetoA.project"

    class ProjectsWithPrimary(object):
        primary = PrimaryProject()

    class FakeSystem(object):
        pass

    report = mod.main({"projects": ProjectsWithPrimary(), "system": FakeSystem()})

    assert report["globals"]["projects_available"] is True
    assert report["globals"]["system_available"] is True
    assert report["project"]["primary_available"] is True
    assert report["project"]["path"] == "C:\\Projetos\\ProjetoA.project"


def test_system_unavailable_reflected_as_false(monkeypatch, tmp_path):
    mod = _load_module(monkeypatch, tmp_path, argv=[str(SCRIPT_PATH)])

    class ProjectsNoPrimary(object):
        pass

    report = mod.main({"projects": ProjectsNoPrimary()})
    assert report["globals"]["system_available"] is False
    assert report["globals_detail"]["system"]["state"] == "unsupported"


def test_system_available_reflected_as_true(monkeypatch, tmp_path):
    mod = _load_module(monkeypatch, tmp_path, argv=[str(SCRIPT_PATH)])

    class FakeSystem(object):
        pass

    report = mod.main({"system": FakeSystem()})
    assert report["globals"]["system_available"] is True
    assert report["globals_detail"]["system"]["state"] == "confirmed"


# =============================================================================
# 2. sys.argv vazio vs. com argumentos simulados
# =============================================================================

def test_argv_empty_is_captured_as_empty_list(monkeypatch, tmp_path):
    mod = _load_module(monkeypatch, tmp_path, argv=[str(SCRIPT_PATH)])
    monkeypatch.setattr(sys, "argv", [])  # simula argv vazio SO na chamada controlada
    report = mod.main({})
    assert report["argv"] == []


def test_argv_with_simulated_scriptargs_is_captured_raw(monkeypatch, tmp_path):
    fake_argv = [str(SCRIPT_PATH), "--project", "C:\\Projetos\\Projeto.project",
                "--scriptargs", "--output C:\\saida", "--noUI"]
    mod = _load_module(monkeypatch, tmp_path, argv=[str(SCRIPT_PATH)])
    monkeypatch.setattr(sys, "argv", fake_argv)
    report = mod.main({})
    assert report["argv"] == fake_argv


# =============================================================================
# 3. as 4 camadas de resolucao de diretorio de saida, isoladas
# =============================================================================

def test_output_dir_layer1_used_when_arg_present_and_writable(monkeypatch, tmp_path):
    mod = _load_module(monkeypatch, tmp_path, argv=[str(SCRIPT_PATH)])
    target = tmp_path / "layer1_out"
    report = {"output_dir_resolution": []}
    resolved = mod._resolve_output_dir(
        [str(SCRIPT_PATH), "--output", str(target)], report)
    assert resolved == str(target)
    assert report["output_dir_resolution"][0]["layer"] == 1
    assert report["output_dir_resolution"][0]["success"] is True


def test_output_dir_layer1_fails_over_to_layer2_when_arg_dir_unwritable(monkeypatch, tmp_path):
    mod = _load_module(monkeypatch, tmp_path, argv=[str(SCRIPT_PATH)])

    calls = []

    def fake_try_write(path):
        calls.append(path)
        if len(calls) == 1:
            return False, "simulado: falha de escrita na camada 1"
        return True, "ok"

    monkeypatch.setattr(mod, "_try_write_to_dir", fake_try_write)

    report = {"output_dir_resolution": []}
    resolved = mod._resolve_output_dir(
        [str(SCRIPT_PATH), "--output", "C:\\caminho\\que\\falha"], report)

    attempts = report["output_dir_resolution"]
    assert attempts[0]["layer"] == 1
    assert attempts[0]["success"] is False
    assert attempts[1]["layer"] == 2
    assert attempts[1]["success"] is True
    assert resolved == calls[1]


def test_output_dir_layer2_fails_over_to_layer3_cwd(monkeypatch, tmp_path):
    mod = _load_module(monkeypatch, tmp_path, argv=[str(SCRIPT_PATH)])

    calls = []

    def fake_try_write(path):
        calls.append(path)
        # sem --output em argv, a camada 1 nunca chama _try_write_to_dir
        # (nao ha candidato) -- a PRIMEIRA chamada real e a camada 2, que
        # deve falhar; a SEGUNDA chamada real e a camada 3 (cwd), que deve
        # ter sucesso.
        if len(calls) == 1:
            return False, "simulado: falha na camada 2"
        return True, "ok (camada 3, cwd)"

    monkeypatch.setattr(mod, "_try_write_to_dir", fake_try_write)

    report = {"output_dir_resolution": []}
    # sem --output em argv -> camada 1 nem tenta escrever (so registra
    # "nenhum argumento reconhecido"); camada 2 (relativo a __file__) falha
    # via fake; camada 3 (cwd) sucede via fake.
    resolved = mod._resolve_output_dir([str(SCRIPT_PATH)], report)

    attempts = report["output_dir_resolution"]
    assert attempts[0]["layer"] == 1
    assert attempts[0]["success"] is False
    assert attempts[0]["candidate"] is None  # nenhum --output em argv
    assert attempts[1]["layer"] == 2
    assert attempts[1]["success"] is False
    assert attempts[2]["layer"] == 3
    assert attempts[2]["success"] is True
    assert resolved is not None


def test_output_dir_all_layers_fail_returns_none_and_records_layer4(monkeypatch, tmp_path):
    mod = _load_module(monkeypatch, tmp_path, argv=[str(SCRIPT_PATH)])

    def always_fail(path):
        return False, "simulado: escrita sempre falha"

    monkeypatch.setattr(mod, "_try_write_to_dir", always_fail)

    report = {"output_dir_resolution": []}
    resolved = mod._resolve_output_dir([str(SCRIPT_PATH)], report)

    assert resolved is None
    attempts = report["output_dir_resolution"]
    layers = [a["layer"] for a in attempts]
    assert 1 in layers and 2 in layers and 3 in layers and 4 in layers
    last = attempts[-1]
    assert last["layer"] == 4
    assert last["success"] is None
    assert "print()" in last["source"]


def test_output_dir_layer2_skipped_when_file_unavailable(monkeypatch, tmp_path):
    mod = _load_module(monkeypatch, tmp_path, argv=[str(SCRIPT_PATH)])
    monkeypatch.setattr(mod, "_FILE_AVAILABLE", False)

    def always_fail(path):
        return False, "falha simulada"

    monkeypatch.setattr(mod, "_try_write_to_dir", always_fail)

    report = {"output_dir_resolution": []}
    mod._resolve_output_dir([str(SCRIPT_PATH)], report)
    layer2 = [a for a in report["output_dir_resolution"] if a["layer"] == 2][0]
    assert layer2["success"] is False
    assert "indisponivel" in layer2["detail"]


def test_output_dir_explicit_command_line_probe_path_writes_result_json(monkeypatch, tmp_path):
    """Confirma, com um caminho no formato pedido pelo usuario
    (workspace/command-line-probe/test-01), que --output funciona e grava
    result.json ali (camada 1 de _resolve_output_dir)."""
    mod = _load_module(monkeypatch, tmp_path, argv=[str(SCRIPT_PATH)])
    target = tmp_path / "workspace" / "command-line-probe" / "test-01"

    fake_argv = [str(SCRIPT_PATH), "--output", str(target)]
    monkeypatch.setattr(sys, "argv", fake_argv)
    report = mod.main({})

    resolution = report["output_dir_resolution"]
    assert resolution[0]["layer"] == 1
    assert resolution[0]["success"] is True
    assert resolution[0]["candidate"] == str(target)

    # o diretorio de execucao real e um subdiretorio timestamped criado por
    # file_io.new_export_dir(target, ...) dentro de target.
    written = list(target.glob("*/result.json"))
    assert len(written) == 1, "result.json nao encontrado sob %s" % target
    data = json.loads(written[0].read_text(encoding="utf-8"))
    assert data["schema_version"] == 1
    assert data["script_started"] is True


# --- parse tolerante de --output (funcao pura, sem I/O) --------------------

def test_find_output_arg_supports_space_equals_and_colon_forms(monkeypatch, tmp_path):
    mod = _load_module(monkeypatch, tmp_path, argv=[str(SCRIPT_PATH)])
    find = mod._find_output_arg

    assert find(["--output", "C:\\a"]) == "C:\\a"
    assert find(["--output=C:\\b"]) == "C:\\b"
    assert find(["--output:C:\\c"]) == "C:\\c"
    assert find(["--other", "x"]) is None
    assert find([]) is None
    assert find(None) is None


def test_find_output_arg_ignores_trailing_output_flag_without_value(monkeypatch, tmp_path):
    mod = _load_module(monkeypatch, tmp_path, argv=[str(SCRIPT_PATH)])
    find = mod._find_output_arg
    # "--output" e o ULTIMO token, sem valor seguinte -> nenhum candidato.
    assert find(["--project", "x", "--output"]) is None


# =============================================================================
# 4. falha simulada em cada passo individual -- os demais e o relatorio final
#    continuam acontecendo mesmo assim
# =============================================================================

def test_interpreter_step_failure_does_not_block_report(monkeypatch, tmp_path):
    mod = _load_module(monkeypatch, tmp_path, argv=[str(SCRIPT_PATH)])

    from common import compatibility
    monkeypatch.setattr(compatibility, "python_version",
                        lambda: (_ for _ in ()).throw(RuntimeError("boom interpreter")))

    report = mod.main({})
    steps_by_name = {s["name"]: s for s in report["steps"]}
    # o passo em si nao falha por completo (varios sub try/except internos),
    # mas os demais passos continuam ok e o relatorio e gravado.
    assert steps_by_name["capture_argv"]["status"] == "ok"
    assert steps_by_name["capture_cwd"]["status"] == "ok"
    assert steps_by_name["check_globals_available"]["status"] == "ok"
    assert steps_by_name["check_project_primary_and_path"]["status"] == "ok"
    assert report["completed_at"] is not None


def test_cwd_step_failure_does_not_block_other_steps(monkeypatch, tmp_path):
    mod = _load_module(monkeypatch, tmp_path, argv=[str(SCRIPT_PATH)])

    import os as os_module
    monkeypatch.setattr(os_module, "getcwd",
                        lambda: (_ for _ in ()).throw(OSError("cwd indisponivel")))

    report = mod.main({})
    steps_by_name = {s["name"]: s for s in report["steps"]}
    assert steps_by_name["capture_cwd"]["status"] == "error"
    assert report["cwd"] is None
    # demais passos seguem rodando
    assert steps_by_name["capture_argv"]["status"] == "ok"
    assert steps_by_name["capture_script_file"]["status"] == "ok"
    assert steps_by_name["capture_interpreter_info"]["status"] == "ok"
    assert steps_by_name["check_globals_available"]["status"] == "ok"
    assert report["completed_at"] is not None


def test_env_step_failure_does_not_block_other_steps(monkeypatch, tmp_path):
    mod = _load_module(monkeypatch, tmp_path, argv=[str(SCRIPT_PATH)])

    class ExplodingEnv(dict):
        def get(self, *a, **k):
            raise RuntimeError("env explodiu")

    import os as os_module
    monkeypatch.setattr(os_module, "environ", ExplodingEnv())

    report = mod.main({})
    steps_by_name = {s["name"]: s for s in report["steps"]}
    # cada var de ambiente e protegida individualmente -> passo completa ok
    # com valores de erro por chave, nunca aborta o passo inteiro.
    assert steps_by_name["capture_safe_env_vars"]["status"] == "ok"
    assert all(isinstance(v, str) and v.startswith("<erro")
              for v in report["env"].values())
    assert report["completed_at"] is not None


def test_globals_step_failure_does_not_block_report(monkeypatch, tmp_path):
    mod = _load_module(monkeypatch, tmp_path, argv=[str(SCRIPT_PATH)])

    from common import compatibility
    monkeypatch.setattr(compatibility, "probe_globals",
                        lambda names, g: (_ for _ in ()).throw(RuntimeError("probe explodiu")))

    report = mod.main({"projects": object()})
    steps_by_name = {s["name"]: s for s in report["steps"]}
    assert steps_by_name["check_globals_available"]["status"] == "error"
    assert report["globals"]["projects_available"] is False
    assert report["globals"]["system_available"] is False
    # o passo seguinte (project_primary_and_path) ainda roda e completa ok,
    # so nao encontra 'projects' (projects_obj fica None nesse cenario).
    assert steps_by_name["check_project_primary_and_path"]["status"] == "ok"
    assert report["project"]["primary_available"] is False
    # relatorio ainda e concluido e outros passos ainda ok
    assert steps_by_name["capture_argv"]["status"] == "ok"
    assert report["completed_at"] is not None


def test_report_writing_failure_falls_back_to_console_without_raising(monkeypatch, tmp_path, capsys):
    mod = _load_module(monkeypatch, tmp_path, argv=[str(SCRIPT_PATH)])

    def fail_resolution(argv, report):
        report["output_dir_resolution"] = [{
            "layer": 4, "source": "print()", "candidate": None,
            "success": None, "detail": "todas as camadas falharam (forcado no teste)",
        }]
        return None

    monkeypatch.setattr(mod, "_resolve_output_dir", fail_resolution)

    report = mod.main({})  # nao deve lancar excecao
    assert report["completed_at"] is not None
    out = capsys.readouterr().out
    assert "Nenhuma camada de escrita em disco funcionou" in out


# =============================================================================
# extra: relatorio gravado em disco tem os campos e o formato exatos exigidos
# =============================================================================

def test_written_result_json_has_expected_top_level_fields_and_types(monkeypatch, tmp_path):
    mod = _load_module(monkeypatch, tmp_path, argv=[str(SCRIPT_PATH)])
    target = tmp_path / "explicit_output"

    class PrimaryProject(object):
        path = "C:\\Projetos\\ProjetoA.project"

    class ProjectsWithPrimary(object):
        primary = PrimaryProject()

    class FakeSystem(object):
        pass

    report = mod.main({"projects": ProjectsWithPrimary(), "system": FakeSystem()})
    # forca gravacao explicita num diretorio conhecido para inspecionar o
    # arquivo real gravado por common.file_io.
    from common import file_io
    run_dir = file_io.new_export_dir(str(target), "validate_command_line_execution")
    file_io.write_json(str(Path(run_dir) / "result.json"), report)
    file_io.write_text(str(Path(run_dir) / "report.md"), mod.report_to_markdown(report))

    written = json.loads((Path(run_dir) / "result.json").read_text(encoding="utf-8"))

    for key in ("schema_version", "script_started", "argv", "runtime", "globals",
               "project", "safety"):
        assert key in written, "campo ausente no result.json: %s" % key

    assert written["schema_version"] == 1
    assert isinstance(written["schema_version"], int)
    assert written["script_started"] is True
    assert isinstance(written["argv"], list)

    runtime = written["runtime"]
    assert set(("platform", "version", "version_info")) <= set(runtime.keys())
    assert runtime["platform"] == sys.platform

    glb = written["globals"]
    assert glb["projects_available"] is True
    assert glb["system_available"] is True
    assert isinstance(glb["projects_available"], bool)
    assert isinstance(glb["system_available"], bool)

    project = written["project"]
    assert project["primary_available"] is True
    assert project["path"] == "C:\\Projetos\\ProjetoA.project"

    safety = written["safety"]
    assert safety == {
        "project_modified": False,
        "save_called": False,
        "build_called": False,
        "online_operation": False,
    }

    md_text = (Path(run_dir) / "report.md").read_text(encoding="utf-8")
    assert "Probe 15" in md_text
    assert "globals.projects_available" in md_text

    # observation.md NUNCA e criado por este script -- e preenchido
    # manualmente pelo usuario, fora deste script.
    assert not (Path(run_dir) / "observation.md").exists()
    assert not (Path(run_dir) / "summary.md").exists()


def test_no_report_json_filename_used_anymore(monkeypatch, tmp_path):
    """O nome de arquivo gravado deve ser result.json, nao mais report.json
    (RENOMEADO conforme pedido explicito do usuario)."""
    mod = _load_module(monkeypatch, tmp_path, argv=[str(SCRIPT_PATH)])
    target = tmp_path / "rename_check"
    fake_argv = [str(SCRIPT_PATH), "--output", str(target)]
    monkeypatch.setattr(sys, "argv", fake_argv)
    mod.main({})

    result_files = list(target.glob("*/result.json"))
    legacy_report_files = list(target.glob("*/report.json"))
    assert len(result_files) == 1
    assert len(legacy_report_files) == 0

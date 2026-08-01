# -*- coding: utf-8 -*-
"""Runner supervisionado interno (`supervised_snapshot`) -- executado DENTRO
do MasterTool pelo `bootstrap.py` gerado pelo host. Contrato:
`docs/16-supervised-runner-contract.md`, secao 6 (sequencia de 14 passos).

Este modulo e so orquestracao fina: toda a navegacao/leitura contra o
projeto vive em `common/read_only_project_scanner.py`,
`common/read_only_text_exporter.py` e `common/graphic_language_inventory.py`
(ja aprovados e cobertos por seus proprios testes). Nada daqui reimplementa
essa logica -- so chama.

`main(run_dir, script_globals)` e a assinatura exata esperada pelo
`bootstrap.py` (contrato, secao 5): `script_globals` e sempre o `globals()`
capturado no escopo do PROPRIO `bootstrap.py`, nunca o `globals()` deste
modulo -- os globais `projects`/`system` injetados pelo ScriptEngine do
CODESYS so existem no escopo do arquivo principal executado
(`--runscript`), nao dentro de modulos importados por ele. Repassar
`script_globals` adiante (para `project_access.get_primary_project`) e
obrigatorio.

Compatibilidade: IronPython 2.7 (sem f-strings, pathlib, type hints,
`os.replace`).
"""
from __future__ import print_function

import os
import sys
import traceback

from automation import run_config, run_status
from common import checksums, file_io, project_access, safety
from common import graphic_language_inventory as inventory_mod
from common import read_only_project_scanner as scanner_mod
from common import read_only_text_exporter as exporter_mod


def _load_ladder_probe_module(mastertool_scripts_dir, probe_filename=None,
                              module_name=None):
    """Carrega um probe (por exemplo, 'probes/16_probe_ladder_object_surface.py')
    como um modulo Python de verdade, pelo CAMINHO -- o nome do arquivo
    comeca com digito ('16_...'/'17_...'), entao
    `import probes.16_probe_ladder_object_surface` e SyntaxError (nome de
    modulo Python nao pode comecar com digito). Usamos dois mecanismos,
    nesta ordem, porque nenhum funciona nos dois runtimes:

      1. `importlib.util.spec_from_file_location` -- caminho do CPython 3.
         Preferido quando existe.
      2. `imp.load_source` -- o unico disponivel em IronPython 2.7, onde este
         runner roda de verdade ('importlib.util' nao existe la).

    A ordem importa: `imp` foi REMOVIDO no CPython 3.12 (e ja emite
    DeprecationWarning no 3.11, onde a suite roda). Tentar `imp` primeiro
    faria a suite quebrar na proxima atualizacao do Python do host, sem
    nenhuma relacao com o MasterTool. Tentar `importlib` primeiro mantem os
    dois runtimes funcionando e sem aviso.

    Nenhum dos dois e dependencia nova: ambos sao biblioteca padrao do
    respectivo runtime. `probe_filename` e `module_name` sao parametrizados
    (generalizado a partir da versao original, hardcoded para o probe 16)
    para que os probes 16 e 17 reutilizem a mesma funcao de carregamento sem
    duplicar os dois mecanismos acima.

    Os dois tem DEFAULT (o probe 16) em vez de serem obrigatorios: a
    generalizacao nao pode quebrar chamadas de uma assinatura ja em uso.
    Tornar os parametros exigidos transformaria uma extensao aditiva em
    mudanca incompativel, e o unico sintoma seria um TypeError em quem ja
    chamava a versao antiga."""
    if probe_filename is None:
        probe_filename = "16_probe_ladder_object_surface.py"
    if module_name is None:
        module_name = "mastertool_bridge_probe_16_ladder_object_surface"
    probe_path = os.path.join(mastertool_scripts_dir, "probes", probe_filename)

    try:
        import importlib.util as _importlib_util
    except ImportError:
        _importlib_util = None

    if _importlib_util is not None and hasattr(_importlib_util, "spec_from_file_location"):
        spec = _importlib_util.spec_from_file_location(module_name, probe_path)
        if spec is None or spec.loader is None:
            raise ImportError("nao foi possivel montar o spec do probe: %s" % probe_path)
        module = _importlib_util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module

    import imp  # IronPython 2.7: unico mecanismo disponivel
    return imp.load_source(module_name, probe_path)


def _check_provenance():
    """Confirma que a execucao atual e IronPython 2.7 rodando via CLI
    (contrato, secao 0: 'dentro do MasterTool -> platform=="cli",
    IronPython, version_info[:2]==[2,7]'). Isolado em funcao propria (em vez
    de inline em main()) para permitir que os testes de unidade rodando em
    CPython 3.11 substituam este unico ponto de decisao (via monkeypatch) e
    exercitem os passos SEGUINTES da sequencia sem precisar de um interprete
    IronPython real -- o comportamento real desta funcao (reprovar fora de
    IronPython 2.7) continua coberto por um teste que a chama diretamente,
    sem substituicao.

    ACHADO REAL da primeira execucao supervisionada (2026-07-24 21:00, run
    `2026-07-24_21-00-43`): a versao anterior desta funcao exigia
    `sys.platform == "cli"` **E** `"IronPython" in sys.version`. Rodando
    dentro do MT8500 3.63 real isso REPROVOU, com
    `platform='cli', IronPython em sys.version=False, version_info[:2]=(2, 7)`
    -- ou seja, dois dos tres sinais corretos e o terceiro ausente.

    Motivo: neste host `sys.version` devolve um BANNER DO PRODUTO, nao um
    texto contendo "IronPython" -- fato ja documentado desde
    `probes/00_smoke_test.py` (e repetido na nota de `runtime` do probe 15:
    "sys.version neste host pode retornar um banner do produto, nao um
    numero de versao"). Por isso `common/compatibility.is_ironpython()` usa
    **OU** (`platform == "cli"` OU o texto), e nao E.

    A correcao e reusar o helper aprovado em vez de reimplementar a regra
    aqui: duas versoes da mesma checagem divergem, e esta divergiu para o
    lado que quebra. `sys.platform == "cli"` continua exigido
    explicitamente porque so o runtime .NET o define, e a versao 2.7
    tambem -- o que se abandona e apenas a exigencia do texto no banner."""
    from common import compatibility

    try:
        version_pair = tuple(sys.version_info[:2])
    except Exception:
        version_pair = None

    ironpython = bool(compatibility.is_ironpython())
    platform_cli = (sys.platform == "cli")
    ok = bool(ironpython and platform_cli and version_pair == (2, 7))
    detail = ("platform=%r, compatibility.is_ironpython()=%r, "
             "'IronPython' em sys.version=%r (irrelevante: este host devolve "
             "banner do produto), version_info[:2]=%r"
             % (sys.platform, ironpython, "IronPython" in sys.version, version_pair))

    # Terceiro retorno: os valores OBSERVADOS, num formato que o host consome
    # direto (cli_probe_verify.check_provenance espera exatamente estas tres
    # chaves sob 'runtime'). Existe porque o host validava a procedencia
    # contra uma secao que o runner NUNCA emitia -- logo toda execucao
    # supervisionada real terminava 'failed' por um motivo sem relacao com a
    # aquisicao. Uma checagem que sempre falha treina o operador a ignorar o
    # status, que e o pior resultado possivel para uma guarda de seguranca.
    #
    # Os valores sao PRESERVADOS mesmo quando a procedencia reprova: o host
    # precisa saber o que foi observado para distinguir "rodou em CPython 3
    # fora do MasterTool" de "campo ausente". Version_info vai como LISTA
    # (JSON nao tem tupla) e completa, nao so o par.
    try:
        version_full = list(sys.version_info[:3])
    except Exception:
        version_full = None
    runtime = {
        "platform": sys.platform,
        "runtime_family": "IronPython" if ironpython else "CPython",
        "version_info": version_full,
        "provenance_confirmed": ok,
    }
    return ok, detail, runtime


def _normalize_path(path):
    """Normalizacao para comparacao de caminhos Windows: absoluto + case-
    insensitive (contrato, secao 6, passo 7: 'normalizado, case-insensitive'
    -- aplicamos o mesmo criterio tambem a run_dir/output_dir, por
    consistencia, ja que sao todos caminhos do mesmo host Windows)."""
    if path is None:
        return None
    try:
        return os.path.normcase(os.path.normpath(os.path.abspath(str(path))))
    except Exception:
        return None


def _paths_equal(path_a, path_b):
    norm_a = _normalize_path(path_a)
    norm_b = _normalize_path(path_b)
    return norm_a is not None and norm_a == norm_b


def _is_within(path, root):
    norm_path = _normalize_path(path)
    norm_root = _normalize_path(root)
    if norm_path is None or norm_root is None:
        return False
    if norm_path == norm_root:
        return True
    return norm_path.startswith(norm_root + os.sep)


def _build_run_report(limits_used, runtime=None):
    """Declaracao final (contrato, secao 7) + 'limits_used' (achado do
    revisor, 2026-07-24: sem registrar os limites de travessia efetivamente
    usados, uma execucao passada nao e auditavel -- nao daria para saber
    depois com que teto de nos/profundidade/caracteres um snapshot foi
    produzido). Os 6 campos da declaracao do contrato continuam presentes,
    sempre False nesta fase (somente leitura) -- nenhuma das operacoes que
    os tornaria True e permitida (ver run_config.py: build/save/online/
    download/force sao todos rejeitados antes de qualquer passo executar).
    'limits_used' e um campo adicional, nao especificado pelo contrato
    original, mas nao remove nem reduz os 6 campos exigidos."""
    return {
        "project_saved": False,
        "build_called": False,
        "online_operation": False,
        "download_called": False,
        "force_called": False,
        "original_project_touched": False,
        "limits_used": limits_used,
        # Procedencia OBSERVADA, vinda de _check_provenance() -- nunca
        # recalculada aqui. Uma segunda deteccao de runtime divergiria da
        # primeira, e a divergencia so apareceria como dois vereditos
        # diferentes sobre a mesma execucao.
        "runtime": runtime if runtime is not None else {},
    }


def main(run_dir, script_globals):
    """Executa a sequencia de 14 passos do contrato (secao 6). Nunca deixa
    uma excecao escapar: qualquer erro nao previsto e capturado, gravado como
    status=failed (com traceback), e um dict de resultado e retornado -- o
    `bootstrap.py` chamador nunca precisa de um try/except em volta desta
    chamada."""
    run_id = os.path.basename(os.path.normpath(run_dir))
    status = run_status.StatusWriter(run_dir, run_id)

    # Banner na aba "Mensagens de script". Sem isto o operador que esta
    # supervisionando com a UI visivel nao tem evidencia nenhuma de que o
    # runner comecou (ver o achado registrado em run_status.set_state).
    try:
        print("=" * 60)
        print("[INFO] supervised_snapshot_runner -- run_id=%s" % run_id)
        print("[INFO] run_dir=%s" % run_dir)
        print("[INFO] %s" % safety.read_only_banner())
    except Exception:
        pass

    result = {
        "run_id": run_id,
        "run_dir": run_dir,
        "final_state": None,
        "abort_reason": None,
        "detail": None,
        "run_report": None,
    }

    def _abort(reason, detail=None, tb=None):
        status.set_state("failed", detail=detail, error=reason, traceback_text=tb)
        result["final_state"] = "failed"
        result["abort_reason"] = reason
        result["detail"] = detail
        return result

    try:
        # Passo 1: escreve status=script_started.
        status.set_state("script_started", detail="bootstrap.py iniciou o runner interno.")

        # Passo 2: valida procedencia (platform/cli + IronPython + 2.7).
        provenance_ok, provenance_detail, provenance_runtime = _check_provenance()
        # Guardado ANTES do teste: o caminho de abort tambem precisa emitir a
        # secao 'runtime' com os valores observados -- e justamente quando a
        # procedencia reprova que saber o que foi observado importa.
        result["runtime"] = provenance_runtime
        if not provenance_ok:
            return _abort("provenance_check_failed", detail=provenance_detail)

        # Passos 3+4: carrega e valida run-config.json (schema_version,
        # campos obrigatorios, 'operations' -- ver run_config.py) e, com o
        # config ja carregado, confere run_dir derivado de __file__ (o
        # parametro run_dir recebido, que o bootstrap.py derivou do seu
        # proprio __file__) contra o run_dir declarado dentro do proprio
        # config. As duas checagens sao feitas juntas porque a segunda
        # depende do config estar carregado -- carregar o arquivo cru duas
        # vezes (uma so pra ler run_dir, outra para validar tudo) duplicaria
        # I/O e logica sem ganho real.
        try:
            config = run_config.load_run_config(run_dir)
        except run_config.RunConfigError as exc:
            return _abort("run_config_invalid", detail=str(exc))

        if not _paths_equal(run_dir, config.get("run_dir")):
            return _abort(
                "run_dir_mismatch",
                detail=("run_dir derivado de __file__ ('%s') difere do run_dir "
                        "declarado em run-config.json ('%s')."
                        % (run_dir, config.get("run_dir"))))

        output_dir = config["output_dir"]
        allowed_output_root = config["allowed_output_root"]
        if not _is_within(output_dir, allowed_output_root):
            return _abort(
                "output_dir_outside_allowed_root",
                detail=("output_dir ('%s') nao esta dentro de allowed_output_root ('%s')."
                        % (output_dir, allowed_output_root)))

        # Passo 5: escreve status=provenance_validated.
        status.set_state(
            "provenance_validated",
            detail="Procedencia IronPython/CLI 2.7 confirmada; run-config.json validado.")

        # Passo 6: resolve projects.primary. script_globals e repassado
        # EXATAMENTE como recebido -- nunca substituido por globals() deste
        # modulo (ver docstring do modulo).
        project, project_error = project_access.get_primary_project(script_globals)
        if project is None:
            return _abort("primary_project_unavailable", detail=project_error)

        # Passo 7: compara projects.primary.path com expected_project_path.
        project_path = project_access.get_project_path(project)
        expected_project_path = config["expected_project_path"]
        if not _paths_equal(project_path, expected_project_path):
            return _abort(
                "project_identity_mismatch",
                detail=("Caminho do projeto aberto ('%s') difere do esperado ('%s')."
                        % (project_path, expected_project_path)))

        try:
            application = getattr(project, "active_application")
        except Exception as exc:
            return _abort("active_application_unavailable", detail=repr(exc))
        if application is None:
            return _abort(
                "active_application_unavailable",
                detail="project.active_application retornou None.")

        # Limites de travessia (achado do revisor, 2026-07-24): sempre
        # explicitos, NUNCA os defaults das classes em common/ -- config ja
        # chegou aqui com 'limits' totalmente preenchido (defaults validados
        # da baseline v0.1.0 aplicados por run_config._resolve_limits() onde
        # o config nao tiver informado um valor).
        limits = config["limits"]
        exporter_limits = limits["exporter"]

        # Passo 8: confirma identidade da Application (name/guid/type_guid).
        # QUEM ABORTA por divergencia e este runner -- a classe generica so
        # RELATA (contrato, secao 6.2). Por isso a checagem e feita ANTES de
        # export()/inventory(): so uma sondagem de identidade, nunca leitura
        # de conteudo. expected_* vem sempre do config, nunca hardcoded
        # (contrato, secao 6.3).
        exporter = exporter_mod.ReadOnlyTextExporter(
            max_depth=exporter_limits["max_depth"],
            max_total_nodes=exporter_limits["max_total_nodes"],
            max_children_per_node=exporter_limits["max_children_per_node"],
            max_text_objects=exporter_limits["max_text_objects"],
            max_document_characters=exporter_limits["max_document_characters"],
            max_total_characters=exporter_limits["max_total_characters"],
            expected_application_name=config["expected_application_name"],
            expected_application_type_guid=config["expected_application_type_guid"],
            expected_application_guid=config["expected_application_guid"])

        identity_mismatches = []
        application_identity = exporter._probe_application_identity(application, identity_mismatches)
        if identity_mismatches:
            return _abort(
                "application_identity_mismatch",
                detail=[m.to_dict() for m in identity_mismatches])

        # Passo 9: escreve status=project_identity_validated.
        status.set_state(
            "project_identity_validated",
            detail="Identidade do projeto e da Application confirmadas.")

        # output_dir nao pode ja conter artefatos (nada e sobrescrito).
        if os.path.isdir(output_dir) and os.listdir(output_dir):
            return _abort(
                "output_dir_not_empty",
                detail="output_dir ('%s') ja contem arquivos -- nada seria sobrescrito." % output_dir)
        file_io.ensure_dir(output_dir)

        operations = config["operations"]

        scan_result = None
        if operations.get("scan_project_tree"):
            # Passo 10: status=scanning -> chama o scanner estrutural.
            status.set_state("scanning", detail="Executando ReadOnlyProjectScanner sobre o projeto.")
            scanner_limits = limits["scanner"]
            scanner = scanner_mod.ReadOnlyProjectScanner(
                max_depth=scanner_limits["max_depth"],
                max_total_nodes=scanner_limits["max_total_nodes"],
                max_children_per_node=scanner_limits["max_children_per_node"],
                expected_root_count=scanner_limits["expected_root_count"])
            scan_result = scanner.scan(project)
            file_io.write_json(os.path.join(output_dir, "project-tree.json"), scan_result["tree"])
            file_io.write_json(os.path.join(output_dir, "project-scan-errors.json"), scan_result["errors"])

        export_result = None
        if operations.get("export_text"):
            # Passo 11: status=exporting -> chama o exportador textual.
            #
            # ACHADO da primeira execucao supervisionada real (2026-07-24):
            # o lado host (build_static_index / load_export, ver
            # src/mastertool_bridge/indexer/export_loader.py) exige, no
            # MINIMO, 4 arquivos em output/ para considerar o export
            # indexavel: manifest.json, flat-objects.json, text-index.json e
            # checksums.sha256. A costura so fecha se os 4 existirem, com
            # manifest.json/flat-objects.json gravados ANTES de
            # checksums.sha256 (senao o checksum nao cobre esses 2 arquivos
            # e verify_checksums() do lado host reprova). flat-objects.json
            # e o MESMO flat_nodes ja calculado aqui (exporter_mod.flatten_tree),
            # nao um artefato novo -- so faltava grava-lo em disco.
            status.set_state("exporting", detail="Executando ReadOnlyTextExporter sobre a Application.")
            export_result = exporter.export(application, output_directory=None)
            exporter_mod.write_text_export_artifacts(export_result, output_dir)
            file_io.write_json(os.path.join(output_dir, "application-tree.json"), export_result["tree"])
            flat_nodes = exporter_mod.flatten_tree(export_result["tree"])
            text_index = exporter_mod.build_text_index(flat_nodes)
            file_io.write_json(os.path.join(output_dir, "flat-objects.json"), flat_nodes)
            file_io.write_json(os.path.join(output_dir, "text-index.json"), text_index)
            file_io.write_json(os.path.join(output_dir, "export-errors.json"), export_result["errors"])

            # manifest.json -- mesmo espirito do probe 13 (schema_version/
            # script/generated_at/mode/exporter_config), mas identificando
            # este runner (nao o probe) e incluindo os limites efetivamente
            # usados (auditoria: com que teto de nos/caracteres este export
            # foi produzido). O host so confere PRESENCA deste arquivo (ver
            # export_loader.REQUIRED_FILES); nao parseia campos especificos
            # dele, entao o formato abaixo e uma escolha deste runner, nao
            # um contrato herdado do probe.
            manifest = {
                "schema_version": "1.0",
                "script": "scripts/mastertool/automation/supervised_snapshot_runner.py (mode=supervised_snapshot)",
                "generated_at": file_io.iso_now(),
                "mode": "read_only",
                "run_id": run_id,
                "exporter_config": {
                    "max_depth": exporter_limits["max_depth"],
                    "max_total_nodes": exporter_limits["max_total_nodes"],
                    "max_children_per_node": exporter_limits["max_children_per_node"],
                    "max_text_objects": exporter_limits["max_text_objects"],
                    "max_document_characters": exporter_limits["max_document_characters"],
                    "max_total_characters": exporter_limits["max_total_characters"],
                    "expected_application_name": config["expected_application_name"],
                    "expected_application_type_guid": config["expected_application_type_guid"],
                    "expected_application_guid": config["expected_application_guid"],
                },
                "limits_used": limits,
            }
            file_io.write_json(os.path.join(output_dir, "manifest.json"), manifest)

        inventory_result = None
        if operations.get("inventory_graphic_objects"):
            # Passo 12 (opcional): inventario grafico, se operations pedir.
            inventory_limits = limits["inventory"]
            engine = inventory_mod.GraphicLanguageInventory(
                max_depth=inventory_limits["max_depth"],
                max_total_nodes=inventory_limits["max_total_nodes"],
                max_children_per_node=inventory_limits["max_children_per_node"],
                expected_application_name=config["expected_application_name"],
                expected_application_type_guid=config["expected_application_type_guid"],
                expected_application_guid=config["expected_application_guid"])
            inventory_mismatches = []
            engine.probe_application_identity(application, inventory_mismatches)
            if inventory_mismatches:
                return _abort(
                    "application_identity_mismatch",
                    detail=[m.to_dict() for m in inventory_mismatches])
            inventory_result = engine.inventory(application)
            flat_inventory_nodes = inventory_mod.flatten_tree(inventory_result["tree"])
            by_state = inventory_mod.split_by_state(flat_inventory_nodes)
            file_io.write_json(
                os.path.join(output_dir, "graphic-language-inventory.json"), flat_inventory_nodes)
            file_io.write_json(
                os.path.join(output_dir, "ladder-objects.json"),
                by_state[inventory_mod.STATE_PARTIALLY_SUPPORTED])
            file_io.write_json(
                os.path.join(output_dir, "unsupported-objects.json"),
                by_state[inventory_mod.STATE_UNSUPPORTED])
            file_io.write_json(os.path.join(output_dir, "inventory-errors.json"), inventory_result["errors"])

        ladder_probe_result = None
        if operations.get("probe_ladder_surface"):
            # Fase L1 (docs/14-ladder-roadmap.md), operacao nova do contrato
            # (secao 3.1). Nenhum estado dedicado existe na maquina de
            # estados fixa do contrato (secao 4, run_status.VALID_STATES) --
            # reutilizamos 'scanning' (mais proximo semanticamente: sondagem
            # de estrutura de UM objeto, nao exportacao de texto), com
            # detail e print() explicitos para nao ficar invisivel na aba de
            # Mensagens (mesmo achado real ja documentado acima para as
            # demais operacoes).
            status.set_state(
                "scanning",
                detail="Executando probe_ladder_surface (Fase L1) sobre o objeto alvo configurado.")
            try:
                print("[INFO] probe_ladder_surface: target_node_id=%s"
                     % config["ladder_probe"]["target_node_id"])
            except Exception:
                pass

            ladder_probe_module = _load_ladder_probe_module(
                config["mastertool_scripts_dir"],
                "16_probe_ladder_object_surface.py",
                "mastertool_bridge_probe_16_ladder_object_surface")
            ladder_output_dir = os.path.join(output_dir, "ladder-surface-probe")
            file_io.ensure_dir(ladder_output_dir)
            ladder_probe_result = ladder_probe_module.probe_ladder_surface(
                application, config["ladder_probe"], ladder_output_dir)

            if ladder_probe_result.get("aborted"):
                return _abort(
                    "ladder_probe_" + str(ladder_probe_result.get("abort_reason")),
                    detail=ladder_probe_result)

            try:
                print("[OK] probe_ladder_surface concluido: candidate_count=%s "
                     "safe_getter_invocations=%s"
                     % (ladder_probe_result.get("candidate_count"),
                        ladder_probe_result.get("safe_getter_invocations")))
            except Exception:
                pass

        ladder_dynamic_probe_result = None
        if operations.get("probe_ladder_dynamic_surface"):
            # Fase L1 (docs/14-ladder-roadmap.md), operacao INDEPENDENTE do
            # probe 16 (flag, secao de config e diretorio de saida proprios --
            # sao sondagens distintas: reflexao CLR estatica vs superficie
            # dinamica, contrato secao 3.1). Ao contrario do probe 16, este
            # tem estado dedicado ('probing_ladder_dynamic_surface', ver
            # run_status.VALID_STATES) porque carrega um GATE DE VALIDADE
            # proprio (o controle 'textual_declaration') cujo resultado
            # decide se o probe e conclusivo ou nao.
            status.set_state(
                "probing_ladder_dynamic_surface",
                detail="Executando probe_ladder_dynamic_surface (Fase L1) sobre o objeto alvo configurado.")
            try:
                print("[INFO] probe_ladder_dynamic_surface: target_node_id=%s"
                     % config["ladder_dynamic_probe"]["target_node_id"])
            except Exception:
                pass

            ladder_dynamic_probe_module = _load_ladder_probe_module(
                config["mastertool_scripts_dir"],
                "17_probe_ladder_dynamic_surface.py",
                "mastertool_bridge_probe_17_ladder_dynamic_surface")
            ladder_dynamic_output_dir = os.path.join(output_dir, "ladder-dynamic-surface")
            file_io.ensure_dir(ladder_dynamic_output_dir)
            ladder_dynamic_probe_result = ladder_dynamic_probe_module.probe_ladder_dynamic_surface(
                application, config["ladder_dynamic_probe"], ladder_dynamic_output_dir)

            if ladder_dynamic_probe_result.get("aborted"):
                return _abort(
                    "ladder_dynamic_probe_" + str(ladder_dynamic_probe_result.get("abort_reason")),
                    detail=ladder_dynamic_probe_result)

            try:
                print("[OK] probe_ladder_dynamic_surface concluido: "
                     "dynamic_probe_validated=%s ladder_candidate_count=%s"
                     % (ladder_dynamic_probe_result.get("dynamic_probe_validated"),
                        ladder_dynamic_probe_result.get("ladder_candidate_count")))
                if not ladder_dynamic_probe_result.get("dynamic_probe_validated"):
                    # Um resultado inconclusivo NUNCA pode parecer sucesso na
                    # aba de Mensagens: o gate de validade (controle
                    # 'textual_declaration') nao confirmou que a superficie
                    # dinamica foi de fato observada, entao nenhuma conclusao
                    # sobre AUSENCIA de API Ladder e permitida a partir deste
                    # resultado.
                    print("[ATENCAO] probe_ladder_dynamic_surface: resultado "
                         "INCONCLUSIVO (dynamic_probe_validated=False). "
                         "Nenhuma conclusao sobre ausencia de API Ladder e "
                         "permitida a partir deste resultado.")
            except Exception:
                pass

        ladder_extender_probe_result = None
        if operations.get("probe_ladder_extender_surface"):
            # Fase L1, terceiro canal: Extender/IExtendedObject. Independente
            # dos probes 16 e 17 (flag, secao e diretorio proprios) e com
            # estado dedicado, porque tem gate distinto dos outros dois:
            # Extender acessivel -> canal enumeravel -> controle
            # 'textual_declaration' REENCONTRADO por caminho estrutural.
            status.set_state(
                "probing_ladder_extender_surface",
                detail="Executando probe_ladder_extender_surface (Fase L1) sobre o objeto alvo configurado.")
            try:
                print("[INFO] probe_ladder_extender_surface: target_node_id=%s"
                     % config["ladder_extender_probe"]["target_node_id"])
            except Exception:
                pass

            ladder_extender_probe_module = _load_ladder_probe_module(
                config["mastertool_scripts_dir"],
                "18_probe_ladder_extender_surface.py",
                "mastertool_bridge_probe_18_ladder_extender_surface")
            ladder_extender_output_dir = os.path.join(output_dir, "ladder-extender-probe")
            file_io.ensure_dir(ladder_extender_output_dir)
            ladder_extender_probe_result = ladder_extender_probe_module.probe_ladder_extender_surface(
                application, config["ladder_extender_probe"], ladder_extender_output_dir)

            if ladder_extender_probe_result.get("aborted"):
                return _abort(
                    "ladder_extender_probe_" + str(ladder_extender_probe_result.get("abort_reason")),
                    detail=ladder_extender_probe_result)

            try:
                print("[OK] probe_ladder_extender_surface concluido: result_case=%s "
                     "extender_channel_validated=%s ladder_candidate_count=%s"
                     % (ladder_extender_probe_result.get("result_case"),
                        ladder_extender_probe_result.get("extender_channel_validated"),
                        ladder_extender_probe_result.get("ladder_candidate_count")))
                if not ladder_extender_probe_result.get("extender_channel_validated"):
                    # E3/E4 sao execucoes CORRETAS que nao confirmaram o
                    # canal -- resultado semantico inconclusivo, NAO falha
                    # operacional. O runner segue para validating/completed;
                    # o que nao pode e o operador ler isso como sucesso.
                    print("[ATENCAO] probe_ladder_extender_surface: canal NAO "
                         "validado (%s). O controle 'textual_declaration' nao "
                         "foi reencontrado por um caminho que passe pelo "
                         "Extender. Resultado INCONCLUSIVO: nenhuma conclusao "
                         "sobre existencia ou ausencia de API Ladder e "
                         "permitida. A execucao em si esta correta -- isto NAO "
                         "e falha do runner."
                         % ladder_extender_probe_result.get("result_case"))
            except Exception:
                pass

        plcopen_signature_result = None
        if operations.get("probe_plcopen_export_signature"):
            # Fase L1, rota de exportacao. Gate proprio: comprovar a
            # assinatura COMPLETA de export_xml SEM invoca-lo. Estado
            # dedicado pelo mesmo motivo dos probes 17/18.
            section = config["plcopen_export_signature_probe"]
            inspect_app = section.get("inspect_active_application", True)
            status.set_state(
                "probing_plcopen_export_signature",
                detail="Executando probe_plcopen_export_signature (Fase L1) -- reflexao "
                      "da assinatura de export_xml, SEM invocacao.")
            try:
                print("[INFO] probe_plcopen_export_signature: target_node_id=%s "
                     "inspect_active_application=%s"
                     % (section["target_node_id"], inspect_app))
            except Exception:
                pass

            plcopen_module = _load_ladder_probe_module(
                config["mastertool_scripts_dir"],
                "19_probe_plcopen_xml_export_signature.py",
                "mastertool_bridge_probe_19_plcopen_export_signature")
            plcopen_output_dir = os.path.join(output_dir, "plcopen-signature-probe")
            file_io.ensure_dir(plcopen_output_dir)
            plcopen_signature_result = plcopen_module.probe_plcopen_export_signature(
                application, section, plcopen_output_dir, inspect_app)

            if plcopen_signature_result.get("aborted"):
                return _abort(
                    "plcopen_signature_" + str(plcopen_signature_result.get("abort_reason")),
                    detail=plcopen_signature_result)

            try:
                print("[OK] probe_plcopen_export_signature concluido: POU=%s Application=%s "
                     "(export_xml NUNCA invocado)"
                     % (plcopen_signature_result.get("target_object_result_case"),
                        plcopen_signature_result.get("active_application_result_case")))
                if plcopen_signature_result.get("result_case") != "S1":
                    # S2/S3 sao execucoes CORRETAS que nao comprovaram uma
                    # sobrecarga invocavel -- resultado semantico
                    # inconclusivo, NAO falha operacional.
                    print("[ATENCAO] probe_plcopen_export_signature: nenhuma sobrecarga "
                         "invocavel com seguranca comprovada no objeto alvo (%s). A "
                         "exportacao permanece NAO autorizada. A execucao em si esta "
                         "correta -- isto NAO e falha do runner."
                         % plcopen_signature_result.get("result_case"))
            except Exception:
                pass

        plcopen_export_result = None
        if operations.get("export_plcopen_xml"):
            # PRIMEIRA operacao que escreve em disco. O `export-root` NAO e
            # criado aqui: quem cria e o host, ANTES de lancar o MasterTool,
            # dentro do diretorio exclusivo da run. Este runner so confere e
            # invoca -- separar quem cria de quem valida evita que o mesmo
            # codigo que precisa do diretorio tambem decida que ele esta bom.
            section = config["plcopen_export"]
            status.set_state(
                "exporting_plcopen_xml",
                detail="Executando export_plcopen_xml (Fase L1) -- UMA invocacao de "
                      "export_xml para diretorio descartavel autorizado.")
            try:
                print("[INFO] export_plcopen_xml: target_node_id=%s leaf=%s"
                     % (section["target_node_id"], section["target_leaf_name"]))
            except Exception:
                pass

            plcopen_export_module = _load_ladder_probe_module(
                config["mastertool_scripts_dir"],
                "20_validate_controlled_plcopen_export.py",
                "mastertool_bridge_probe_20_controlled_plcopen_export")
            # `export-root` e criado AQUI, depois de output_dir ja ter
            # passado na guarda de "vazio" -- portanto nasce vazio por
            # construcao, garantia mais forte que cria-lo antes e conferir
            # depois. Pre-cria-lo no host fazia aquela guarda abortar toda a
            # execucao (run 2026-07-28_11-37-05).
            #
            # A separacao "quem cria nao e quem valida" continua: este runner
            # cria, o probe 20 valida existencia/vazio/reparse point/sentinel
            # antes de invocar. O sentinel registra QUEM criou, para o
            # artefato arquivado nao depender de memoria.
            plcopen_export_dir = os.path.join(output_dir, "plcopen-export")
            file_io.ensure_dir(plcopen_export_dir)
            plcopen_export_root = os.path.join(plcopen_export_dir, "export-root")
            file_io.ensure_dir(plcopen_export_root)
            file_io.write_json(
                os.path.join(plcopen_export_dir, "export-root-preparation.json"),
                {
                    "export_root_created_by": "internal_runner",
                    "export_root_created_after": "output_dir_empty_check",
                    "export_root_initially_empty": not os.listdir(plcopen_export_root),
                    "export_root_path": plcopen_export_root,
                    "run_id": config.get("run_id"),
                })
            plcopen_export_result = plcopen_export_module.probe_controlled_plcopen_export(
                application, section, plcopen_export_dir)

            if plcopen_export_result.get("aborted"):
                return _abort(
                    "plcopen_export_" + str(plcopen_export_result.get("abort_reason")),
                    detail=plcopen_export_result)

            try:
                print("[OK] export_plcopen_xml concluido: result_case=%s entradas_criadas=%s"
                     % (plcopen_export_result.get("result_case"),
                        plcopen_export_result.get("created_entry_count")))
                print("[INFO] O FORMATO do que foi produzido NAO e decidido aqui: a "
                     "analise do XML roda no host, em CPython, depois que o "
                     "MasterTool fechar.")
            except Exception:
                pass

        # Passo 13: status=validating -> confere artefatos + checksums.
        status.set_state("validating", detail="Conferindo artefatos gravados e gerando checksums.")
        expected_artifacts = []
        if operations.get("scan_project_tree"):
            expected_artifacts.append("project-tree.json")
        if operations.get("export_text"):
            expected_artifacts.append("application-tree.json")
            expected_artifacts.append("flat-objects.json")
            expected_artifacts.append("manifest.json")
        if operations.get("inventory_graphic_objects"):
            expected_artifacts.append("graphic-language-inventory.json")
        if operations.get("probe_ladder_surface"):
            expected_artifacts.append(os.path.join("ladder-surface-probe", "manifest.json"))
            expected_artifacts.append(os.path.join("ladder-surface-probe", "safety-declaration.json"))
        if operations.get("probe_ladder_dynamic_surface"):
            expected_artifacts.append(os.path.join("ladder-dynamic-surface", "manifest.json"))
            expected_artifacts.append(os.path.join("ladder-dynamic-surface", "control-validation.json"))
        if operations.get("export_plcopen_xml"):
            for _name in ("invocation.json", "filesystem-before.json",
                          "filesystem-after.json", "created-artifacts.json",
                          "safety-declaration.json"):
                expected_artifacts.append(os.path.join("plcopen-export", _name))
        if operations.get("probe_plcopen_export_signature"):
            expected_artifacts.append(os.path.join("plcopen-signature-probe", "manifest.json"))
            expected_artifacts.append(
                os.path.join("plcopen-signature-probe", "export-xml-overloads.json"))
            expected_artifacts.append(
                os.path.join("plcopen-signature-probe", "active-application-overloads.json"))
        if operations.get("probe_ladder_extender_surface"):
            expected_artifacts.append(os.path.join("ladder-extender-probe", "manifest.json"))
            # Sem este artefato nao ha como saber se o canal foi validado.
            expected_artifacts.append(os.path.join("ladder-extender-probe", "known-control-discovery.json"))
        missing_artifacts = [
            name for name in expected_artifacts
            if not os.path.isfile(os.path.join(output_dir, name))
        ]
        if missing_artifacts:
            return _abort(
                "expected_artifacts_missing",
                detail="Artefatos esperados nao encontrados em output_dir: %s" % missing_artifacts)
        checksums.write_checksums_file(output_dir, os.path.join(output_dir, "checksums.sha256"))

        # Passo 14: grava a declaracao final e status=completed.
        run_report = _build_run_report(limits, result.get("runtime"))
        file_io.write_json(os.path.join(output_dir, "run-report.json"), run_report)
        status.set_state("completed", detail="Aquisicao supervisionada concluida.")

        result["final_state"] = "completed"
        result["run_report"] = run_report

        # Instrucao final ao operador. Este runner NAO fecha o MasterTool (e
        # somente leitura, nunca fecha projeto), e o orquestrador de host fica
        # bloqueado esperando o processo encerrar antes de conferir o hash
        # final, validar artefatos e rodar o indexador.
        #
        # ACHADO REAL da execucao 2026-07-24_21-21-01: sem esta mensagem o
        # operador nao tinha como saber que faltava uma acao DELE. A aquisicao
        # terminou em 4 s e o host ficou parado esperando, com a UI aberta e a
        # aba de Mensagens vazia -- indistinguivel de "travou".
        try:
            print("[OK] Aquisicao concluida. Artefatos em: %s" % output_dir)
            print("")
            print(">>> ACAO NECESSARIA: FECHE o MasterTool para o orquestrador")
            print(">>> seguir (hash final, validacao de artefatos e indexador).")
            print(">>> Este script nao fecha o MasterTool por conta propria.")
            print("=" * 60)
        except Exception:
            pass

        return result

    except Exception as exc:
        tb_text = traceback.format_exc()
        try:
            status.set_state(
                "failed", detail="Excecao nao prevista durante a aquisicao.",
                error=repr(exc), traceback_text=tb_text)
        except Exception:
            pass
        result["final_state"] = "failed"
        result["abort_reason"] = "unexpected_exception"
        result["detail"] = repr(exc)
        result["traceback"] = tb_text
        return result

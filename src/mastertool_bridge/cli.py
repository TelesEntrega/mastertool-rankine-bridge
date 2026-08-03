"""CLI externa `mastertool-bridge` (argparse — sem dependências extras).

Todos os comandos operam sobre exports em disco; nenhum toca o MasterTool
ou o CLP.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from mastertool_bridge import __version__
from mastertool_bridge.automation.run_states import STATE_COMPLETED
from mastertool_bridge.exceptions import BridgeError, ValidationError
from mastertool_bridge.logging_config import setup_logging
from mastertool_bridge.utils.json_io import write_json


def _print_json(data) -> None:
    print(json.dumps(data, indent=2, ensure_ascii=False, default=str))


def cmd_validate_export(args) -> int:
    from mastertool_bridge.export.validator import validate_export
    result = validate_export(Path(args.export_dir),
                             check_checksums=not args.skip_checksums)
    print(result.summary())
    for error in result.errors:
        print(f"  ERRO: {error}")
    for warning in result.warnings:
        print(f"  AVISO: {warning}")
    return 0 if result.ok else 1


def cmd_inspect(args) -> int:
    from mastertool_bridge.export.loader import load_export
    project = load_export(Path(args.export_dir))
    stats = {t: len(objs) for t, objs in sorted(project.objects_by_type().items())}
    _print_json({
        "project": project.name,
        "export_dir": str(project.export_dir),
        "read_only": project.is_read_only,
        "manifest_statistics": project.manifest.get("statistics", {}),
        "objects_loaded": len(project.objects),
        "objects_by_type": stats,
    })
    return 0


def cmd_index(args) -> int:
    from mastertool_bridge.export.indexer import build_index
    from mastertool_bridge.export.loader import load_export
    project = load_export(Path(args.export_dir))
    index = build_index(project)
    output = Path(args.output) if args.output else (
        Path(args.export_dir) / "reports" / "index.json")
    write_json(output, index)
    print(f"Índice gravado em {output} "
          f"({len(index['objects'])} objetos, {len(index['variables'])} variáveis).")
    return 0


def cmd_analyze(args) -> int:
    from mastertool_bridge.analysis.report_generator import safety_report_markdown
    from mastertool_bridge.analysis.safety_checks import check_project
    from mastertool_bridge.export.loader import load_export
    project = load_export(Path(args.export_dir))
    findings = check_project(project)
    report = safety_report_markdown(project, findings)
    output = Path(args.output) if args.output else (
        Path(args.export_dir) / "reports" / "safety-report.md")
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(report, encoding="utf-8", newline="\n")
    print(f"{len(findings)} alerta(s) heurístico(s). Relatório: {output}")
    return 0


def cmd_document(args) -> int:
    from mastertool_bridge.docs.dependency_documenter import document_dependencies
    from mastertool_bridge.docs.project_documenter import document_project
    from mastertool_bridge.export.loader import load_export
    project = load_export(Path(args.export_dir))
    out_dir = Path(args.output) if args.output else (
        Path(args.export_dir) / "reports")
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "project-documentation.md").write_text(
        document_project(project), encoding="utf-8", newline="\n")
    (out_dir / "dependencies.md").write_text(
        document_dependencies(project), encoding="utf-8", newline="\n")
    print(f"Documentação gerada em {out_dir}")
    return 0


def cmd_compare(args) -> int:
    from mastertool_bridge.diff.project_diff import compare_projects
    from mastertool_bridge.export.loader import load_export
    old = load_export(Path(args.export_a))
    new = load_export(Path(args.export_b))
    result = compare_projects(old, new)
    if args.output:
        write_json(Path(args.output), result)
    print(result["summary"])
    for item in result["modified"]:
        print(f"  modificado: {item['object']}")
    for name in result["added"]:
        print(f"  adicionado: {name}")
    for name in result["removed"]:
        print(f"  removido:   {name}")
    return 0


def _find_symbol_refs(args, mode: str) -> int:
    from mastertool_bridge.analysis.reference_finder import (
        filter_reads, filter_writes, find_references)
    from mastertool_bridge.export.loader import load_export
    project = load_export(Path(args.export_dir))
    references = find_references(project, args.symbol,
                                 include_declarations=(mode == "all"))
    if mode == "writes":
        references = filter_writes(references)
    elif mode == "reads":
        references = filter_reads(references)
    _print_json({
        "schema_version": "1.0",
        "symbol": args.symbol,
        "heuristic": True,
        "note": "Classificação heurística — revisar manualmente.",
        "references": [r.to_dict() for r in references],
    })
    return 0


def cmd_find_symbol(args) -> int:
    return _find_symbol_refs(args, "all")


def cmd_find_writes(args) -> int:
    return _find_symbol_refs(args, "writes")


def cmd_find_reads(args) -> int:
    return _find_symbol_refs(args, "reads")


def cmd_build_agent_context(args) -> int:
    from mastertool_bridge.docs.project_documenter import document_project
    from mastertool_bridge.export.indexer import build_index
    from mastertool_bridge.export.loader import load_export
    project = load_export(Path(args.export_dir))
    out_dir = Path(args.output) if args.output else (
        Path(args.export_dir) / "reports" / "agent-context")
    out_dir.mkdir(parents=True, exist_ok=True)
    write_json(out_dir / "index.json", build_index(project))
    (out_dir / "project-overview.md").write_text(
        document_project(project), encoding="utf-8", newline="\n")
    (out_dir / "SAFETY.md").write_text(
        "# Contexto para agentes de IA\n\n"
        "Este material é SOMENTE LEITURA. Regras completas em AGENTS.md do "
        "repositório. Não invente APIs do MasterTool; não proponha operações "
        "online; toda alteração vira change set com aprovação humana.\n",
        encoding="utf-8", newline="\n")
    print(f"Contexto para agentes gerado em {out_dir}")
    return 0


def cmd_validate_change_set(args) -> int:
    from mastertool_bridge.changes.change_set import load_change_set
    from mastertool_bridge.changes.validator import validate_change_set_policy
    try:
        change_set = load_change_set(Path(args.change_set_file))
    except ValidationError as exc:
        print(f"[FALHOU] {exc}")
        for issue in exc.issues:
            print(f"  ERRO (schema): {issue}")
        return 1
    result = validate_change_set_policy(change_set)
    print(result.summary())
    print(f"  risco mais alto: {change_set.highest_risk}")
    for error in result.errors:
        print(f"  ERRO (política): {error}")
    for warning in result.warnings:
        print(f"  AVISO: {warning}")
    return 0 if result.ok else 1


def cmd_qualify_repeatability(args) -> int:
    """Agrega N gerações já produzidas e emite o veredito da fase R1.

    Não lança o MasterTool e não executa nada: o lote é rodado pelo operador,
    em sessão supervisionada, e este comando julga o que ficou em disco. A
    separação é a mesma de sempre — quem executa é a sessão, quem verifica é
    o host.
    """
    from mastertool_bridge.automation.generation_equivalence import (
        LAYOUT_FACTORY,
        LAYOUT_W1_4,
        compare_many,
    )

    layouts = {"factory": LAYOUT_FACTORY, "w1-4": LAYOUT_W1_4}
    layout = layouts[args.layout]

    raiz = Path(args.runs_root)
    if not raiz.is_dir():
        print(f"[FALHOU] diretório de lote não encontrado: {raiz}")
        return 1

    # Ordem lexicográfica dos diretórios `run-NNN` coincide com a ordem de
    # execução, por causa da largura fixa na numeração.
    corridas = sorted(d for d in raiz.iterdir()
                      if d.is_dir() and d.name.startswith("run-"))
    if not corridas:
        print(f"[FALHOU] nenhum diretório `run-*` em {raiz}")
        return 1

    # `run_project_factory.ps1` grava tudo sob `<WorkRoot>/artefatos/`, e é lá
    # que `verificacao/` e `execution-completion.json` ficam. Olhar direto para
    # `run-NNN/` encontraria o diretório e nenhum artefato — e o veredito sairia
    # "árvore ausente ou ilegível" para um lote perfeitamente bom.
    #
    # A resolução é por EXISTÊNCIA, não por convenção: quem passa um diretório
    # que já é o de artefatos continua funcionando.
    geracoes = []
    for corrida in corridas:
        artefatos = corrida / "artefatos"
        geracoes.append(artefatos if artefatos.is_dir() else corrida)

    resultado = compare_many(geracoes, layout=layout,
                             minimum_required=args.minimum)

    print(f"lote: {len(geracoes)} geração(ões) em {raiz}")
    print(f"  piso da norma      : {resultado.minimum_required}"
          f" ({'atingido' if resultado.meets_minimum else 'NÃO atingido'})")
    print(f"  equivalentes       : {resultado.equivalent_count}"
          f"/{len(resultado.per_generation)}")
    print(f"  independência      : "
          f"{'ok' if not resultado.independence_violations else 'VIOLADA'}")
    for violacao in resultado.independence_violations:
        print(f"    - {violacao}")
    for geracao in resultado.per_generation:
        if geracao["equivalent"]:
            continue
        print(f"  DIVERGE {geracao['generation']}")
        for divergencia in geracao["divergences"]:
            print(f"    - {divergencia}")
    for campo in resultado.volatile_distribution:
        print(f"  volátil permitido  : {campo['field']} — "
              f"{campo['distinct_values']} valor(es) distinto(s) em "
              f"{campo['observed_in']} geração(ões)")
    for problema in resultado.problems:
        print(f"  PROBLEMA: {problema}")

    print(f"[{'OK' if resultado.repeatable else 'REPROVADO'}] "
          f"repetibilidade: {resultado.repeatable}")

    if args.output:
        write_json(Path(args.output), resultado.to_dict())
        print(f"  relatório: {args.output}")

    if args.html:
        from mastertool_bridge.reports.qualification_report import (
            render_qualification_report,
        )

        # O ativo da marca vive fora deste repositório, então ele entra por
        # parâmetro. Sem ele o documento sai sem logo — e não com um logo
        # inventado.
        logo = None
        if args.logo_file:
            logo = Path(args.logo_file).read_text(encoding="utf-8").strip()

        html = render_qualification_report(
            resultado.to_dict(), generated_at=args.generated_at,
            qualification_id=args.qualification_id,
            template_profile=args.template_profile,
            product_version=args.product_version,
            logo_data_uri=logo)
        Path(args.html).write_text(html, encoding="utf-8", newline="\n")
        print(f"  documento: {args.html}")

    return 0 if resultado.repeatable else 1


def _ler_versao_de_arquivo(caminho: str) -> str | None:
    """Versão de produto de um `.exe` no Windows, sem dependência externa.

    Devolve `None` fora do Windows ou quando o recurso de versão não existe —
    e `None` NUNCA significa "a versão está certa": quem exige versão trata a
    ausência como recusa. Ver `mastertool_detect`.
    """
    import ctypes
    import ctypes.wintypes as wintypes

    try:
        version_dll = ctypes.WinDLL("version.dll")  # type: ignore[attr-defined]
    except (AttributeError, OSError):
        return None

    try:
        tamanho = version_dll.GetFileVersionInfoSizeW(
            ctypes.c_wchar_p(caminho), None)
        if not tamanho:
            return None
        buffer = ctypes.create_string_buffer(tamanho)
        if not version_dll.GetFileVersionInfoW(
                ctypes.c_wchar_p(caminho), 0, tamanho, buffer):
            return None
        ponteiro = ctypes.c_void_p()
        comprimento = wintypes.UINT()
        if not version_dll.VerQueryValueW(
                buffer, ctypes.c_wchar_p("\\"),
                ctypes.byref(ponteiro), ctypes.byref(comprimento)):
            return None

        class _FixedFileInfo(ctypes.Structure):
            _fields_ = [
                ("dwSignature", wintypes.DWORD),
                ("dwStrucVersion", wintypes.DWORD),
                ("dwFileVersionMS", wintypes.DWORD),
                ("dwFileVersionLS", wintypes.DWORD),
                ("dwProductVersionMS", wintypes.DWORD),
                ("dwProductVersionLS", wintypes.DWORD),
                ("dwFileFlagsMask", wintypes.DWORD),
                ("dwFileFlags", wintypes.DWORD),
                ("dwFileOS", wintypes.DWORD),
                ("dwFileType", wintypes.DWORD),
                ("dwFileSubtype", wintypes.DWORD),
                ("dwFileDateMS", wintypes.DWORD),
                ("dwFileDateLS", wintypes.DWORD),
            ]

        info = ctypes.cast(ponteiro,
                           ctypes.POINTER(_FixedFileInfo)).contents
        return "%d.%d.%d.%d" % (
            info.dwFileVersionMS >> 16, info.dwFileVersionMS & 0xFFFF,
            info.dwFileVersionLS >> 16, info.dwFileVersionLS & 0xFFFF)
    except Exception:  # noqa: BLE001 — falha de leitura é ausência de versão
        return None


def _ler_gate_do_codigo(repo_root: Path):
    """`CONTROLLED_WRITE_PHASE` lido por AST, sem importar o módulo.

    O `safety.py` é escrito para IronPython 2.7 e roda dentro do produto;
    importá-lo aqui para ler uma constante executaria código que não foi
    escrito para este interpretador. A AST lê o literal e nada mais.
    """
    import ast

    caminho = repo_root / "scripts" / "mastertool" / "common" / "safety.py"
    arvore = ast.parse(caminho.read_text(encoding="utf-8"))
    for no in arvore.body:
        if not isinstance(no, ast.Assign):
            continue
        for alvo in no.targets:
            if isinstance(alvo, ast.Name) and alvo.id == "CONTROLLED_WRITE_PHASE":
                return ast.literal_eval(no.value)
    raise ValueError("CONTROLLED_WRITE_PHASE não encontrado em safety.py")


def cmd_check_unexpected_changes(args) -> int:
    """Prova que só os alvos declarados mudaram — o invariante da fase R2."""
    import json as _json

    from mastertool_bridge.diff.unexpected_changes import compare

    def _ler(caminho):
        if not caminho:
            return None
        try:
            return _json.loads(Path(caminho).read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return None

    autorizadas = []
    if args.authorized_file:
        conteudo = _ler(args.authorized_file)
        if isinstance(conteudo, list):
            autorizadas = conteudo
        elif isinstance(conteudo, dict):
            autorizadas = conteudo.get("authorized") or []
    autorizadas = list(autorizadas) + list(args.authorized or [])

    relatorio = compare(_ler(args.before_nodes), _ler(args.after_nodes),
                        _ler(args.before_texts), _ler(args.after_texts),
                        authorized=autorizadas)

    print(f"veredito: {relatorio.verdict}")
    for rotulo, itens in (("objeto acrescentado", relatorio.added_objects),
                          ("objeto removido", relatorio.removed_objects),
                          ("texto NÃO autorizado alterado",
                           relatorio.unauthorized_text_changes)):
        for item in itens:
            print(f"  [ACHADO] {rotulo}: {item}")
    for item in relatorio.authorized_and_changed:
        print(f"  [ok] autorizado e alterado: {item}")
    for item in relatorio.authorized_but_unchanged:
        print(f"  [nota] autorizado e SEM efeito: {item}")
    for problema in relatorio.problems:
        print(f"  PROBLEMA: {problema}")

    if relatorio.clean:
        print("[OK] só o autorizado mudou.")
    elif relatorio.verdict == "incomparable":
        print("[INCOMPARÁVEL] a comparação não foi possível — e isso não é "
              "'nada mudou'.")
    else:
        print("[ACHADO] há mudança que ninguém autorizou.")

    if args.output:
        write_json(Path(args.output), relatorio.to_dict())
        print(f"  registro: {args.output}")

    return 0 if relatorio.clean else 2


def cmd_emit_rollback_spec(args) -> int:
    """Emite a spec que DESFAZ as alterações de uma execução (fase R2).

    Offline e puro: lê o plano e o `before-texts.json` que a execução gravou, e
    devolve a spec inversa. Não abre o MasterTool e **não adivinha texto** — se
    a execução não registrou o conteúdo anterior, isto recusa, em vez de emitir
    uma spec com `text: ""` que apagaria o objeto com cara de reversão.
    """
    from mastertool_bridge.changes.rollback import build_rollback_spec

    resultado = build_rollback_spec(
        _read_json_or_none(args.plan),
        _read_json_or_none(args.before_texts),
        output_project_sha256=args.target_project_sha256)

    for problema in resultado.problems:
        print(f"  PROBLEMA: {problema}")
    for item in resultado.reverted:
        print(f"  [reverte] {item}")

    if not resultado.ok:
        print("[BLOQUEADO] a reversão não pôde ser emitida. Isso não é "
              "'nada a reverter' — é falta de dado para reverter.")
        return 2

    if args.output:
        write_json(Path(args.output), resultado.spec)
        print(f"  spec de reversão: {args.output}")
    else:
        _print_json(resultado.spec)
    print("[OK] spec inversa emitida.")
    return 0


def cmd_package_run(args) -> int:
    """Empacota uma execução da fábrica num Evidence Bundle selado.

    `evidence/from_run.package_run` existia desde a fundação da R2 e **não
    tinha chamador**: o pacote só podia ser montado de dentro de um teste.
    Uma capacidade sem porta de entrada é uma capacidade que ninguém usa, e o
    que ninguém usa não é exercido contra o campo.

    Sela mesmo incompleto, e o código de saída distingue os dois: `sealed`
    sai 0, `sealed_incomplete` sai 3. A execução que deu errado é a que mais
    precisa ficar registrada — o que ela não pode é sair como completa.
    """
    from mastertool_bridge.evidence.from_run import package_run

    resultado = package_run(
        args.run_dir, args.bundle_root, args.run_id,
        spec_path=args.spec,
        source_project_sha256=args.source_project_sha256,
        unexpected_changes=_read_json_or_none(args.unexpected_changes),
        rollback_spec=_read_json_or_none(args.rollback_spec))

    for problema in resultado.problems:
        print(f"  PROBLEMA: {problema}")
    for item in resultado.packaged:
        print(f"  [ok] {item}")
    for item in resultado.missing:
        print(f"  [FALTANDO] {item}")

    if resultado.bundle_root:
        print(f"pacote: {resultado.bundle_root}")
    print(f"status: {resultado.status}")

    # O vocabulário vem de `evidence/bundle.py`, e é importado em vez de
    # escrito de novo: um literal solto aqui deixaria de valer no dia em que
    # o pacote ganhasse um status novo, e o comando diria "completo" por não
    # reconhecer o que leu.
    from mastertool_bridge.evidence.bundle import STATUS_SEALED_COMPLETE

    if resultado.status == STATUS_SEALED_COMPLETE:
        print("[OK] pacote completo e selado.")
        return 0
    if resultado.status is None:
        print("[BLOQUEADO] o pacote não chegou a ser selado.")
        return 2
    print("[INCOMPLETO] selado com artefato faltando. Faltando não é ausente "
          "de importância — é ausente do registro.")
    return 3


def _read_json_or_none(caminho):
    """Lê um JSON opcional. Ausente e ilegível dão o mesmo `None` aqui de
    propósito: quem decide o que fazer com a ausência é `package_run`, que a
    registra como faltando no manifesto."""
    import json as _json

    if not caminho:
        return None
    try:
        return _json.loads(Path(caminho).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def cmd_verify_modifications(args) -> int:
    """Confere os hashes anteriores de uma spec contra um inventário medido.

    Roda ANTES de qualquer sessão de escrita. É a etapa que impede um
    `expected_before_sha256` digitado de memória de virar autorização.
    """
    import json as _json

    from mastertool_bridge.spec.modification_source import (
        load_text_inventory,
        verify_modifications,
    )

    spec = _json.loads(Path(args.spec).read_text(encoding="utf-8"))
    bruto = _json.loads(Path(args.inventory).read_text(encoding="utf-8"))
    inventario = load_text_inventory(
        bruto, project_sha256=args.inventory_project_sha256)

    resultado = verify_modifications(
        spec, inventario,
        expected_project_sha256=args.expected_project_sha256)

    for verificado in resultado.verified:
        print(f"  [ok] {verificado}")
    for problema in resultado.problems:
        print(f"  [RECUSADO] {problema}")

    if resultado.ok and not resultado.verified:
        print("[OK] nada a conferir: a spec não declara `modifications`.")
    elif resultado.ok:
        print(f"[OK] {len(resultado.verified)} alteração(ões) conferida(s) "
              "contra o inventário medido.")
    else:
        print(f"[RECUSADO] {len(resultado.problems)} problema(s). A sessão de "
              "escrita não deve começar.")

    if args.output:
        write_json(Path(args.output), resultado.to_dict())
        print(f"  registro: {args.output}")

    return 0 if resultado.ok else 2


def cmd_preflight_batch(args) -> int:
    """Precondições da sessão de lote, conferidas ANTES de abrir o produto."""
    import hashlib
    import os
    import subprocess

    from mastertool_bridge.automation.batch_preflight import (
        PreflightEnvironment,
        PreflightRequest,
        refusal_report,
        run_preflight,
    )
    from mastertool_bridge.automation.mastertool_detect import (
        Environment as DetectEnvironment,
    )
    from mastertool_bridge.automation.mastertool_detect import detect_mastertool

    repo_root = (Path(args.repo_root) if args.repo_root
                 else Path(__file__).resolve().parents[2])

    def _git(*argumentos: str) -> str:
        return subprocess.check_output(
            ["git", *argumentos], cwd=str(repo_root),
            stderr=subprocess.STDOUT).decode("utf-8", errors="replace").strip()

    def _sha256(caminho: str) -> str | None:
        try:
            digest = hashlib.sha256()
            with open(caminho, "rb") as arquivo:
                for bloco in iter(lambda: arquivo.read(65536), b""):
                    digest.update(bloco)
            return digest.hexdigest()
        except OSError:
            return None

    def _listar_runs(raiz: str) -> list[str]:
        try:
            return sorted(nome for nome in os.listdir(raiz)
                          if nome.startswith("run-")
                          and os.path.isdir(os.path.join(raiz, nome)))
        except OSError:
            return []

    def _plano_existe(dir_run: str) -> bool:
        return os.path.isfile(os.path.join(dir_run, "artefatos",
                                           "authoring-plan.json"))

    ambiente = PreflightEnvironment(
        git_head=lambda: _git("rev-parse", "--short", "HEAD"),
        git_tree_clean=lambda: _git("status", "--porcelain") == "",
        sha256_of=_sha256,
        path_exists=os.path.exists,
        list_run_dirs=_listar_runs,
        plan_output_exists=_plano_existe,
        read_controlled_write_phase=lambda: _ler_gate_do_codigo(repo_root),
        detect_mastertool=lambda: detect_mastertool(
            explicit_path=args.mastertool_exe,
            expected_version=args.expected_mastertool_version,
            env=DetectEnvironment(getenv=os.environ.get,
                                  read_version=_ler_versao_de_arquivo)),
    )

    pedido = PreflightRequest(
        spec_path=args.spec,
        expected_spec_sha256=args.expected_spec_sha256,
        template_path=args.template,
        expected_template_sha256=args.expected_template_sha256,
        template_profile_id=args.template_profile_id,
        output_root=args.output_root,
        requested_runs=args.runs,
        requested_stage=args.stage,
        mastertool_wrapper_path=args.mastertool_exe or "",
        expected_mastertool_version=args.expected_mastertool_version,
        timestamp=args.timestamp,
    )

    resultado = run_preflight(pedido, ambiente)

    registro = resultado.record
    print(f"HEAD               : {registro.get('head')}")
    print(f"árvore limpa       : {registro.get('git_tree_clean')}")
    print(f"gate               : {registro.get('controlled_write_phase')!r}")
    print(f"spec sha256        : {registro.get('spec_sha256')}")
    print(f"template sha256    : {registro.get('template_sha256')}")
    print(f"MasterTool         : {registro.get('mastertool_detected_path')} "
          f"(v{registro.get('mastertool_version')})")
    print(f"caminhos batem     : {registro.get('mastertool_paths_match')}")
    print(f"estágio            : {registro.get('requested_stage')} "
          f"× {registro.get('requested_runs')}")
    print("")
    print("conferido SÓ do lado do host: "
          + "; ".join(registro.get("host_side_only", [])))
    print("reavaliado dentro do MasterTool: "
          + "; ".join(registro.get("reevaluated_in_mastertool", [])))

    if resultado.cleared:
        print("\n[LIBERADO] precondições conferidas. A sessão pode começar.")
    else:
        print("\n" + refusal_report(resultado))

    if args.output:
        write_json(Path(args.output), resultado.to_dict())
        print(f"\n  registro: {args.output}")

    return 0 if resultado.cleared else 2


def cmd_detect_mastertool(args) -> int:
    """Descobre o executável do MasterTool sem fixá-lo em código.

    Não abre o produto: só localiza e, quando pedido, confere a versão.
    """
    import os

    from mastertool_bridge.automation.mastertool_detect import (
        Environment,
        detect_mastertool,
        refusal_reason,
    )

    def _resolver_atalho(caminho: str) -> str | None:
        """Resolve `.lnk` pelo shell do Windows. Fora do Windows — ou sem o
        COM disponível — devolve `None` em vez de levantar: não conseguir
        resolver é um resultado, e o chamador tem outras fontes."""
        try:
            import win32com.client  # type: ignore[import-not-found]
        except Exception:  # noqa: BLE001
            return None
        try:
            shell = win32com.client.Dispatch("WScript.Shell")
            return shell.CreateShortcut(caminho).TargetPath or None
        except Exception:  # noqa: BLE001
            return None

    ambiente = Environment(getenv=os.environ.get,
                           resolve_shortcut=_resolver_atalho,
                           read_version=_ler_versao_de_arquivo)
    resultado = detect_mastertool(
        explicit_path=args.exe, shortcut_path=args.shortcut,
        expected_version=args.expected_version, env=ambiente)

    for caminho in resultado.searched:
        print(f"  procurou: {caminho}")
    for candidato in resultado.candidates:
        print(f"  candidato: {candidato}")

    if resultado.resolved:
        instalacao = resultado.install
        print(f"[OK] {instalacao.exe_path}")
        print(f"     fonte: {instalacao.source}")
        print(f"     versão: {instalacao.version or '(não lida)'}")
    else:
        print(f"[RECUSADO] {refusal_reason(resultado)}")

    if args.output:
        write_json(Path(args.output), resultado.to_dict())
        print(f"  relatório: {args.output}")

    return 0 if resultado.resolved else 1


def cmd_verify_cli_probe(args) -> int:
    from mastertool_bridge.automation.cli_probe_verify import cmd_verify_cli_probe as _run
    return _run(args)


def cmd_supervised_snapshot(args) -> int:
    from pathlib import Path as _Path

    from mastertool_bridge.automation.config_models import RunOperations
    from mastertool_bridge.automation.supervised_run import orchestrate_run
    from mastertool_bridge.utils.json_io import write_json

    # --probe-ladder-surface exige os 4 valores do alvo. A incoerência JÁ é
    # rejeitada mais adiante, na construção do RunConfig (ConfigValidationError),
    # e isso acontece antes de qualquer lançamento do MasterTool — a propriedade
    # fail-closed não depende desta checagem. Ela existe para o operador receber
    # uma mensagem de CLI clara em vez de um traceback, e para falhar no ponto
    # mais barato possível.
    if args.probe_ladder_surface:
        faltando = [
            flag for flag, valor in (
                ("--ladder-target-node-id", args.ladder_target_node_id),
                ("--ladder-expected-name", args.ladder_expected_name),
                ("--ladder-expected-guid", args.ladder_expected_guid),
                ("--ladder-expected-type-guid", args.ladder_expected_type_guid),
            ) if not (valor or "").strip()
        ]
        if faltando:
            print("erro: --probe-ladder-surface exige a identificação completa do "
                  "alvo. Faltando: " + ", ".join(faltando))
            print("Os 25 candidatos da Fase L0 compartilham o mesmo type_guid, "
                  "então os quatro campos são necessários juntos "
                  "(ver docs/16-supervised-runner-contract.md, seção 3.1).")
            return 2

    # Mesma guarda para o probe 17. Deliberadamente separada da do probe 16:
    # as duas operacoes sao independentes e podem ser ligadas isoladamente,
    # entao uma checagem compartilhada esconderia qual das duas esta
    # incompleta.
    if args.probe_ladder_dynamic_surface:
        faltando = [
            flag for flag, valor in (
                ("--ladder-dynamic-target-node-id", args.ladder_dynamic_target_node_id),
                ("--ladder-dynamic-expected-name", args.ladder_dynamic_expected_name),
                ("--ladder-dynamic-expected-guid", args.ladder_dynamic_expected_guid),
                ("--ladder-dynamic-expected-type-guid", args.ladder_dynamic_expected_type_guid),
            ) if not (valor or "").strip()
        ]
        if faltando:
            print("erro: --probe-ladder-dynamic-surface exige a identificacao completa "
                  "do alvo. Faltando: " + ", ".join(faltando))
            print("Os 4 campos sao exigidos juntos: os candidatos da Fase L0 "
                  "compartilham o mesmo type_guid, entao nenhum campo isolado "
                  "identifica o alvo. No modo supervisionado nao ha default de "
                  "identidade (ver docs/16-supervised-runner-contract.md, secao 3.1).")
            return 2

    if args.probe_ladder_extender_surface:
        faltando = [
            flag for flag, valor in (
                ("--ladder-extender-target-node-id", args.ladder_extender_target_node_id),
                ("--ladder-extender-expected-name", args.ladder_extender_expected_name),
                ("--ladder-extender-expected-guid", args.ladder_extender_expected_guid),
                ("--ladder-extender-expected-type-guid", args.ladder_extender_expected_type_guid),
            ) if not (valor or "").strip()
        ]
        if faltando:
            print("erro: --probe-ladder-extender-surface exige a identificacao completa "
                  "do alvo. Faltando: " + ", ".join(faltando))
            print("Os 4 campos sao exigidos juntos e nao ha default de identidade no "
                  "modo supervisionado (ver docs/16-supervised-runner-contract.md, secao 3.1).")
            return 2

    if args.probe_plcopen_export_signature:
        faltando = [
            flag for flag, valor in (
                ("--plcopen-target-node-id", args.plcopen_target_node_id),
                ("--plcopen-expected-name", args.plcopen_expected_name),
                ("--plcopen-expected-guid", args.plcopen_expected_guid),
                ("--plcopen-expected-type-guid", args.plcopen_expected_type_guid),
            ) if not (valor or "").strip()
        ]
        if faltando:
            print("erro: --probe-plcopen-export-signature exige a identificacao completa "
                  "do alvo. Faltando: " + ", ".join(faltando))
            print("Os 4 campos sao exigidos juntos e nao ha default de identidade no "
                  "modo supervisionado.")
            return 2

    if args.export_plcopen_xml:
        faltando = [
            flag for flag, valor in (
                ("--export-target-node-id", args.export_target_node_id),
                ("--export-expected-name", args.export_expected_name),
                ("--export-expected-guid", args.export_expected_guid),
                ("--export-expected-type-guid", args.export_expected_type_guid),
            ) if not (valor or "").strip()
        ]
        if faltando:
            print("erro: --export-plcopen-xml exige a identificacao completa do alvo. "
                  "Faltando: " + ", ".join(faltando))
            print("Nenhum default de identidade e aceito no modo supervisionado -- esta "
                  "operacao ESCREVE em disco.")
            return 2

    # As CINCO operacoes de investigacao sao mutuamente exclusivas numa run: canais
    # distintos, gates proprios, vereditos que nao podem competir sob um
    # unico status. Recusado aqui, no ponto mais barato, alem de no
    # RunConfig e no runner interno.
    _probes_ligados = [
        nome for nome, ligado in (
            ("--probe-ladder-surface", args.probe_ladder_surface),
            ("--probe-ladder-dynamic-surface", args.probe_ladder_dynamic_surface),
            ("--probe-ladder-extender-surface", args.probe_ladder_extender_surface),
            ("--probe-plcopen-export-signature", args.probe_plcopen_export_signature),
            ("--export-plcopen-xml", args.export_plcopen_xml),
        ) if ligado
    ]
    if len(_probes_ligados) > 1:
        print("erro: mais de um probe de investigacao ligado na mesma run: "
              + ", ".join(_probes_ligados))
        print("Cada probe investiga um canal distinto e tem gate de validade "
              "proprio; rode um por vez.")
        return 2

    repo_root = _Path(args.repo_root) if args.repo_root else _Path(__file__).resolve().parents[2]
    mastertool_scripts_dir = (
        _Path(args.mastertool_scripts_dir) if args.mastertool_scripts_dir
        else repo_root / "scripts" / "mastertool")

    operations = RunOperations(
        scan_project_tree=not args.no_scan,
        export_text=not args.no_export_text,
        probe_ladder_surface=args.probe_ladder_surface,
        probe_ladder_dynamic_surface=args.probe_ladder_dynamic_surface,
        probe_ladder_extender_surface=args.probe_ladder_extender_surface,
        probe_plcopen_export_signature=args.probe_plcopen_export_signature,
        export_plcopen_xml=args.export_plcopen_xml,
    )

    ladder_probe = None
    if args.probe_ladder_surface:
        ladder_probe = {
            "target_node_id": args.ladder_target_node_id,
            "expected_name": args.ladder_expected_name,
            "expected_guid": args.ladder_expected_guid,
            "expected_type_guid": args.ladder_expected_type_guid,
        }

    ladder_dynamic_probe = None
    if args.probe_ladder_dynamic_surface:
        ladder_dynamic_probe = {
            "target_node_id": args.ladder_dynamic_target_node_id,
            "expected_name": args.ladder_dynamic_expected_name,
            "expected_guid": args.ladder_dynamic_expected_guid,
            "expected_type_guid": args.ladder_dynamic_expected_type_guid,
        }

    ladder_extender_probe = None
    if args.probe_ladder_extender_surface:
        ladder_extender_probe = {
            "target_node_id": args.ladder_extender_target_node_id,
            "expected_name": args.ladder_extender_expected_name,
            "expected_guid": args.ladder_extender_expected_guid,
            "expected_type_guid": args.ladder_extender_expected_type_guid,
        }

    plcopen_export_signature_probe = None
    if args.probe_plcopen_export_signature:
        plcopen_export_signature_probe = {
            "target_node_id": args.plcopen_target_node_id,
            "expected_name": args.plcopen_expected_name,
            "expected_guid": args.plcopen_expected_guid,
            "expected_type_guid": args.plcopen_expected_type_guid,
            "inspect_active_application": not args.no_inspect_active_application,
        }

    plcopen_export = None
    if args.export_plcopen_xml:
        plcopen_export = {
            "target_node_id": args.export_target_node_id,
            "expected_name": args.export_expected_name,
            "expected_guid": args.export_expected_guid,
            "expected_type_guid": args.export_expected_type_guid,
            "target_leaf_name": args.export_target_leaf_name,
            "recursive": False,
            "export_folder_structure": False,
            "plain_text": False,
        }

    result = orchestrate_run(
        project_copy=args.project_copy,
        original_project=args.original_project,
        runs_root=args.runs_root,
        mastertool_exe=args.mastertool_exe,
        repo_root=repo_root,
        mastertool_scripts_dir=mastertool_scripts_dir,
        expected_application_name=args.expected_application_name,
        expected_application_guid=args.expected_application_guid,
        expected_application_type_guid=args.expected_application_type_guid,
        timeout_seconds=args.timeout,
        run_index=not args.no_index,
        operations=operations,
        ladder_probe=ladder_probe,
        ladder_dynamic_probe=ladder_dynamic_probe,
        ladder_extender_probe=ladder_extender_probe,
        plcopen_export_signature_probe=plcopen_export_signature_probe,
        plcopen_export=plcopen_export,
    )

    report = result.to_dict()
    if args.output:
        write_json(Path(args.output), report)
    _print_json(report)
    return 0 if result.final_state == STATE_COMPLETED else 1


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="mastertool-bridge",
        description=("Camada externa do mastertool-rankine-bridge (somente leitura: "
                     "lê exports; nunca toca o MasterTool nem o CLP)."))
    parser.add_argument("--version", action="version",
                        version=f"%(prog)s {__version__}")
    parser.add_argument("--log-level", default="INFO")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("validate-export", help="Valida manifesto, schemas e checksums")
    p.add_argument("export_dir")
    p.add_argument("--skip-checksums", action="store_true")
    p.set_defaults(func=cmd_validate_export)

    p = sub.add_parser("inspect", help="Resumo de um export")
    p.add_argument("export_dir")
    p.set_defaults(func=cmd_inspect)

    p = sub.add_parser("index", help="Gera índice de objetos e variáveis")
    p.add_argument("export_dir")
    p.add_argument("--output")
    p.set_defaults(func=cmd_index)

    p = sub.add_parser("analyze", help="Verificações de segurança (heurísticas)")
    p.add_argument("export_dir")
    p.add_argument("--output")
    p.set_defaults(func=cmd_analyze)

    p = sub.add_parser("document", help="Gera documentação Markdown do export")
    p.add_argument("export_dir")
    p.add_argument("--output")
    p.set_defaults(func=cmd_document)

    p = sub.add_parser("compare", help="Compara dois exports")
    p.add_argument("export_a")
    p.add_argument("export_b")
    p.add_argument("--output")
    p.set_defaults(func=cmd_compare)

    p = sub.add_parser("find-symbol", help="Todas as referências a um símbolo")
    p.add_argument("export_dir")
    p.add_argument("symbol")
    p.set_defaults(func=cmd_find_symbol)

    p = sub.add_parser("find-writes", help="Escritas (heurísticas) de uma variável")
    p.add_argument("export_dir")
    p.add_argument("symbol")
    p.set_defaults(func=cmd_find_writes)

    p = sub.add_parser("find-reads", help="Leituras (heurísticas) de uma variável")
    p.add_argument("export_dir")
    p.add_argument("symbol")
    p.set_defaults(func=cmd_find_reads)

    p = sub.add_parser("build-agent-context",
                       help="Pacote de contexto (índice + docs) para agentes de IA")
    p.add_argument("export_dir")
    p.add_argument("--output")
    p.set_defaults(func=cmd_build_agent_context)

    p = sub.add_parser("validate-change-set",
                       help="Valida change set contra schema e política de segurança")
    p.add_argument("change_set_file")
    p.set_defaults(func=cmd_validate_change_set)

    p = sub.add_parser(
        "qualify-repeatability",
        help=("Fase R1: julga N gerações já produzidas (diretórios `run-NNN`) "
              "como CONJUNTO — equivalência contra referência e independência "
              "entre todos os pares. Não abre o MasterTool."))
    p.add_argument("--runs-root", required=True,
                   help="Diretório raiz do lote, contendo run-001, run-002, ...")
    p.add_argument("--layout", choices=("factory", "w1-4"), default="factory",
                   help=("Layout de artefato. EXPLÍCITO de propósito: adivinhar "
                         "pelo arquivo presente escolheria em silêncio, e "
                         "escolher errado compararia camadas diferentes."))
    p.add_argument("--minimum", type=int, default=None,
                   help=("Piso de execuções independentes. Padrão: o da norma "
                         "(R1), lido de MIN_INDEPENDENT_RUNS — passar um valor "
                         "menor não afrouxa a fase, só documenta um ensaio."))
    p.add_argument("--output", help="Grava o relatório completo neste JSON")
    p.add_argument("--html", help=("Gera o documento HTML autocontido (padrão "
                                   "visual Rankine) neste caminho"))
    p.add_argument("--generated-at", default="",
                   help=("Carimbo de emissão do documento, ISO 8601. Entra "
                         "como DADO: o gerador não lê o relógio, para que dois "
                         "relatórios do mesmo lote sejam comparáveis byte a "
                         "byte."))
    p.add_argument("--logo-file", help=("Arquivo com o data URI do logo "
                                        "(base64). Sem ele o documento sai "
                                        "sem logo, nunca com um inventado."))
    p.add_argument("--qualification-id", help="Identificador da qualificação")
    p.add_argument("--template-profile", help="`profile_id` do Template Profile")
    p.add_argument("--product-version", help="Produto e versão, ex. 'MasterTool X 4.1.0.11'")
    p.set_defaults(func=cmd_qualify_repeatability)

    p = sub.add_parser(
        "check-unexpected-changes",
        help=("Fase R2: compara antes×depois e prova que só os alvos "
              "declarados mudaram. Artefato ausente sai INCOMPARÁVEL, que "
              "nunca é 'nada mudou'."))
    p.add_argument("--before-nodes", required=True)
    p.add_argument("--after-nodes", required=True)
    p.add_argument("--before-texts", required=True)
    p.add_argument("--after-texts", required=True)
    p.add_argument("--authorized", action="append",
                   help="Chave `familia:nome:campo` autorizada (repetível)")
    p.add_argument("--authorized-file",
                   help="JSON com a lista de chaves autorizadas")
    p.add_argument("--output", help="Grava `unexpected_changes.json` aqui")
    p.set_defaults(func=cmd_check_unexpected_changes)

    p = sub.add_parser(
        "package-run",
        help=("Fase R2: empacota uma execução da fábrica num Evidence Bundle "
              "selado. Sela mesmo incompleto — e sai 3 quando incompleto, "
              "para que 'faltou artefato' nunca passe por 'deu certo'."))
    p.add_argument("--run-dir", required=True,
                   help="Raiz da run (a que contém `artefatos/`)")
    p.add_argument("--bundle-root", required=True,
                   help="Onde o pacote é criado")
    p.add_argument("--run-id", required=True)
    p.add_argument("--spec", help="Spec canônica, copiada para `plan/`")
    p.add_argument("--source-project-sha256",
                   help=("Hash do projeto de ENTRADA. Ausente entra como "
                         "faltando: o pacote não o calcula sozinho, porque "
                         "não tem como saber de qual arquivo se partiu."))
    p.add_argument("--unexpected-changes",
                   help="JSON de `check-unexpected-changes`")
    p.add_argument("--rollback-spec",
                   help=("Spec inversa, de `emit-rollback-spec`. Plano COM "
                         "alteração e sem ela sela incompleto."))
    p.set_defaults(func=cmd_package_run)

    p = sub.add_parser(
        "emit-rollback-spec",
        help=("Fase R2: emite a spec que DESFAZ as alterações de uma "
              "execução. Recusa quando o texto anterior não foi registrado — "
              "reverter sem ele seria apagar o objeto."))
    p.add_argument("--plan", required=True,
                   help="Plano de autoria normalizado da execução")
    p.add_argument("--before-texts", required=True,
                   help=("`execucao/before-texts.json` — o CONTEÚDO anterior, "
                         "gravado no instante em que o hash foi conferido."))
    p.add_argument("--target-project-sha256",
                   help=("sha256 da SAÍDA da execução, que é o alvo da "
                         "reversão. Sem ele cai para o template do plano, que "
                         "é o arquivo errado: ele não tem o texto novo."))
    p.add_argument("--output", help="Grava a spec inversa neste JSON")
    p.set_defaults(func=cmd_emit_rollback_spec)

    p = sub.add_parser(
        "verify-modifications",
        help=("Fase R2: confere cada `expected_before_sha256` da spec contra "
              "um inventário de textos MEDIDO. Fail-closed — divergência "
              "impede a sessão de escrita."))
    p.add_argument("--spec", required=True)
    p.add_argument("--inventory", required=True,
                   help=("Artefato de textos medidos de uma sessão READ-ONLY "
                         "(forma de `factory-verify-texts.json`)."))
    p.add_argument("--inventory-project-sha256",
                   help="De qual projeto o inventário foi medido")
    p.add_argument("--expected-project-sha256",
                   help=("Projeto sobre o qual a spec vai operar. Se diferir "
                         "do inventário, recusa: um hash anterior só vale para "
                         "o arquivo onde foi medido."))
    p.add_argument("--output", help="Grava o resultado neste JSON")
    p.set_defaults(func=cmd_verify_modifications)

    p = sub.add_parser(
        "preflight-batch",
        help=("Confere as precondições de um lote de repetibilidade ANTES de "
              "abrir o produto. Fail-closed: qualquer recusa impede a sessão."))
    p.add_argument("--spec", required=True)
    p.add_argument("--expected-spec-sha256", required=True)
    p.add_argument("--template", required=True)
    p.add_argument("--expected-template-sha256", required=True)
    p.add_argument("--template-profile-id", required=True)
    p.add_argument("--output-root", required=True)
    p.add_argument("--runs", type=int, required=True)
    p.add_argument("--stage", choices=("plan", "build"), required=True)
    p.add_argument("--mastertool-exe", required=True,
                   help=("Caminho que o wrapper usa. É comparado com o "
                         "detectado: se divergirem, o lote mediria um produto "
                         "e o wrapper abriria outro."))
    p.add_argument("--expected-mastertool-version", default="4.1.0.11")
    p.add_argument("--timestamp", required=True,
                   help="ISO 8601. Entra como dado, não é lido do relógio.")
    p.add_argument("--repo-root")
    p.add_argument("--output", help="Grava o registro do preflight neste JSON")
    p.set_defaults(func=cmd_preflight_batch)

    p = sub.add_parser(
        "detect-mastertool",
        help=("Localiza o executável do MasterTool (explícito, "
              "$MASTERTOOL_EXE, atalho .lnk ou busca) e confere a versão. "
              "Duas instalações RECUSAM em vez de escolher uma."))
    p.add_argument("--exe", help="Caminho explícito; ganha de todas as fontes")
    p.add_argument("--shortcut", help="Atalho .lnk a resolver (regra de docs/27)")
    p.add_argument("--expected-version",
                   help=("Versão exigida, ex. 4.1.0.11. Versão diferente "
                         "RECUSA: capacidade provada numa versão não se "
                         "presume provada em outra."))
    p.add_argument("--output", help="Grava o resultado completo neste JSON")
    p.set_defaults(func=cmd_detect_mastertool)

    p = sub.add_parser("verify-cli-probe",
                       help=("Verifica o gate da Etapa A (roadmap de automação) a partir dos "
                             "result.json do probe 15 (--runscript/--scriptargs/--project/"
                             # `%%`: argparse INTERPOLA `help=` contra um
                             # dicionario, e `% o` virava conversao `%o`.
                             # `--help` do CLI inteiro morria por causa desta
                             # string -- e so dela.
                             "--noUI), 100%% offline"))
    p.add_argument("--results-dir", required=True,
                   help="Diretório contendo os result.json (ou subdiretórios) dos testes t1/t2/t4/t5")
    p.add_argument("--output", help="Grava o relatório de gate completo neste arquivo JSON")
    p.add_argument("--expected", help="Arquivo JSON com o que o operador pediu/confirmou "
                                      "(output_dir, project_path, t3_manual_confirmed, "
                                      "t5_manual_confirmed)")
    p.set_defaults(func=cmd_verify_cli_probe)

    p = sub.add_parser(
        "supervised-snapshot",
        help=("Etapa B: orquestra, do lado HOST, uma execução supervisionada do "
             "MT8500 sobre uma cópia descartável do projeto (--project + "
             "--runscript=bootstrap.py, UI visível, sem --scriptargs/--noUI). "
             "Ver docs/16-supervised-runner-contract.md"))
    p.add_argument("--project-copy", required=True,
                   help="Cópia DESCARTÁVEL do .project. NUNCA o projeto original.")
    p.add_argument("--original-project", required=True,
                   help="Projeto original, só para a checagem de 'você não apontou para o original'.")
    p.add_argument("--runs-root", required=True,
                   help="Diretório raiz onde o workspace de execução (<runs-root>/<run-id>/) é criado.")
    p.add_argument("--timeout", type=float, default=900.0,
                   help="Timeout em segundos aguardando o MasterTool encerrar (padrão: 900).")
    p.add_argument("--no-index", action="store_true",
                   help="Não roda o indexador Python 3 sobre o export produzido.")
    p.add_argument("--mastertool-exe",
                   default=r"C:\Program Files (x86)\Altus\MT8500 3.63\MT8500\Common\MT8500.exe",
                   help="Caminho do MT8500.exe.")
    p.add_argument("--repo-root",
                   help="Raiz do repositório (padrão: derivada deste arquivo).")
    p.add_argument("--mastertool-scripts-dir",
                   help="Diretório scripts/mastertool (padrão: <repo-root>/scripts/mastertool).")
    p.add_argument("--expected-application-name", required=True,
                   help="Nome esperado da Application ativa (identidade, contrato seção 2).")
    p.add_argument("--expected-application-guid", required=True,
                   help="GUID esperado da Application ativa (identidade, contrato seção 2).")
    p.add_argument("--expected-application-type-guid", required=True,
                   help="GUID de tipo esperado da Application ativa (identidade, contrato seção 2).")
    p.add_argument("--no-scan", action="store_true",
                   help="Desliga operations.scan_project_tree (padrão: ligado).")
    p.add_argument("--no-export-text", action="store_true",
                   help="Desliga operations.export_text (padrão: ligado). Se ligado junto com "
                        "--run-index (padrão), a execução é reprovada por configuração "
                        "incoerente — passe também --no-index.")
    p.add_argument("--probe-ladder-surface", action="store_true",
                   help=("Liga operations.probe_ladder_surface (Fase L1 — sondagem de "
                         "superfície de API sobre um único objeto POU). Exige os quatro "
                         "--ladder-* abaixo. Ver docs/16-supervised-runner-contract.md seção 3.1."))
    p.add_argument("--ladder-target-node-id",
                   help="ladder_probe.target_node_id — obrigatório com --probe-ladder-surface.")
    p.add_argument("--ladder-expected-name",
                   help="ladder_probe.expected_name — obrigatório com --probe-ladder-surface.")
    p.add_argument("--ladder-expected-guid",
                   help="ladder_probe.expected_guid — obrigatório com --probe-ladder-surface.")
    p.add_argument("--ladder-expected-type-guid",
                   help="ladder_probe.expected_type_guid — obrigatório com --probe-ladder-surface.")
    p.add_argument("--probe-ladder-dynamic-surface", action="store_true",
                   help=("Liga operations.probe_ladder_dynamic_surface (Fase L1 — sondagem "
                         "da superficie DINAMICA via dir()/hasattr(), complementar a "
                         "reflexao CLR do probe 16). Exige os quatro --ladder-dynamic-* "
                         "abaixo. Ver docs/16-supervised-runner-contract.md secao 3.1."))
    p.add_argument("--ladder-dynamic-target-node-id",
                   help="ladder_dynamic_probe.target_node_id — obrigatorio com --probe-ladder-dynamic-surface.")
    p.add_argument("--ladder-dynamic-expected-name",
                   help="ladder_dynamic_probe.expected_name — obrigatorio com --probe-ladder-dynamic-surface.")
    p.add_argument("--ladder-dynamic-expected-guid",
                   help="ladder_dynamic_probe.expected_guid — obrigatorio com --probe-ladder-dynamic-surface.")
    p.add_argument("--ladder-dynamic-expected-type-guid",
                   help="ladder_dynamic_probe.expected_type_guid — obrigatorio com --probe-ladder-dynamic-surface.")
    p.add_argument("--probe-ladder-extender-surface", action="store_true",
                   help=("Liga operations.probe_ladder_extender_surface (Fase L1 -- canal "
                         "Extender/IExtendedObject: providers e descriptors). Exige os "
                         "quatro --ladder-extender-* abaixo. Mutuamente exclusivo com os "
                         "outros probes Ladder."))
    p.add_argument("--ladder-extender-target-node-id",
                   help="ladder_extender_probe.target_node_id -- obrigatorio com --probe-ladder-extender-surface.")
    p.add_argument("--ladder-extender-expected-name",
                   help="ladder_extender_probe.expected_name -- obrigatorio com --probe-ladder-extender-surface.")
    p.add_argument("--ladder-extender-expected-guid",
                   help="ladder_extender_probe.expected_guid -- obrigatorio com --probe-ladder-extender-surface.")
    p.add_argument("--ladder-extender-expected-type-guid",
                   help="ladder_extender_probe.expected_type_guid -- obrigatorio com --probe-ladder-extender-surface.")
    p.add_argument("--probe-plcopen-export-signature", action="store_true",
                   help=("Liga operations.probe_plcopen_export_signature (Fase L1 -- reflexao "
                         "da assinatura COMPLETA de export_xml, SEM invoca-lo). Exige os "
                         "quatro --plcopen-* abaixo. Mutuamente exclusivo com os outros probes."))
    p.add_argument("--plcopen-target-node-id",
                   help="plcopen_export_signature_probe.target_node_id -- obrigatorio.")
    p.add_argument("--plcopen-expected-name",
                   help="plcopen_export_signature_probe.expected_name -- obrigatorio.")
    p.add_argument("--plcopen-expected-guid",
                   help="plcopen_export_signature_probe.expected_guid -- obrigatorio.")
    p.add_argument("--plcopen-expected-type-guid",
                   help="plcopen_export_signature_probe.expected_type_guid -- obrigatorio.")
    p.add_argument("--no-inspect-active-application", action="store_true",
                   help=("Pula a reflexao do escopo Application. O artefato registra "
                         "attempted=false, NUNCA found=false -- 'nao procurei' e diferente "
                         "de 'nao existe'."))
    p.add_argument("--export-plcopen-xml", action="store_true",
                   help=("Liga operations.export_plcopen_xml (Fase L1 -- UMA invocacao de "
                         "export_xml para diretorio descartavel autorizado). ESCREVE em "
                         "disco. Exige os quatro --export-* abaixo. Mutuamente exclusivo "
                         "com os probes de investigacao."))
    p.add_argument("--export-target-node-id", help="plcopen_export.target_node_id -- obrigatorio.")
    p.add_argument("--export-expected-name", help="plcopen_export.expected_name -- obrigatorio.")
    p.add_argument("--export-expected-guid", help="plcopen_export.expected_guid -- obrigatorio.")
    p.add_argument("--export-expected-type-guid",
                   help="plcopen_export.expected_type_guid -- obrigatorio.")
    p.add_argument("--export-target-leaf-name", default="pou-export",
                   help=("Nome SIMPLES do alvo dentro de export-root (sem separador, "
                         "drive ou '..'). Deve nao existir antes da chamada."))
    p.add_argument("--output", help="Grava o relatório consolidado neste arquivo JSON.")
    p.set_defaults(func=cmd_supervised_snapshot, _parser=p)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if getattr(args, "command", None) == "supervised-snapshot" and args.probe_ladder_surface:
        missing = [flag for flag, value in (
            ("--ladder-target-node-id", args.ladder_target_node_id),
            ("--ladder-expected-name", args.ladder_expected_name),
            ("--ladder-expected-guid", args.ladder_expected_guid),
            ("--ladder-expected-type-guid", args.ladder_expected_type_guid),
        ) if not value]
        if missing:
            error_parser = getattr(args, "_parser", parser)
            error_parser.error(
                "--probe-ladder-surface exige também: " + ", ".join(missing))

    setup_logging(args.log_level)
    try:
        return args.func(args)
    except BridgeError as exc:
        print(f"ERRO: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())

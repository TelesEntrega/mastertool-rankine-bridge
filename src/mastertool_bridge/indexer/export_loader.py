"""Carregamento de exports do ReadOnlyTextExporter para o StaticProjectIndexer.

Formato consumido (gerado por `common/read_only_text_exporter.py`, ver
`docs/12-read-only-text-export.md`):

    manifest.json, report.json, application-tree.json, flat-objects.json,
    text-index.json, errors.json, checksums.sha256,
    objects/<node_id_seguro>__<nome_seguro>/{metadata.json, declaration.st,
    implementation.st}

Este módulo NUNCA abre o MasterTool nem faz IO de rede — só lê arquivos já
exportados no disco local. Falha em um objeto nunca impede o processamento
dos demais (mesma filosofia de isolamento de falha do lado IronPython).
"""

from __future__ import annotations

from pathlib import Path

from mastertool_bridge.indexer.call_resolver import (
    build_callers_index,
    resolve_calls,
)
from mastertool_bridge.indexer.declaration_parser import parse_declaration
from mastertool_bridge.indexer.diagnostics import Diagnostic, DiagnosticsCollector
from mastertool_bridge.indexer.dut_parser import parse_dut_declaration
from mastertool_bridge.indexer.gvl_parser import parse_gvl_declaration
from mastertool_bridge.indexer.models import Call, PouSymbol, Reference, TypeSymbol
from mastertool_bridge.indexer.models import ExportBundle
from mastertool_bridge.indexer.reference_resolver import (
    build_read_write_index,
    resolve_references,
)
from mastertool_bridge.indexer.source_model import SourceFile, SourceMap
from mastertool_bridge.indexer.statement_parser import parse_implementation
from mastertool_bridge.indexer.symbol_resolver import ProjectSymbolIndex
from mastertool_bridge.models.validation import ValidationResult
from mastertool_bridge.utils.hashing import verify_checksums
from mastertool_bridge.utils.json_io import read_json, write_json

REQUIRED_FILES = (
    "manifest.json",
    "flat-objects.json",
    "text-index.json",
    "checksums.sha256",
)


def load_export(export_dir: Path) -> ExportBundle:
    """Carrega e valida a estrutura de um export do ReadOnlyTextExporter.

    Não lança exceção para condições esperadas de export incompleto/
    inválido (arquivo ausente, checksum divergente) — reporta tudo via
    `ValidationResult`, deixando o chamador decidir se aborta (`result.ok`).
    """
    export_dir = Path(export_dir)
    result = ValidationResult(subject=f"export:{export_dir}")

    if not export_dir.exists() or not export_dir.is_dir():
        result.add_error(f"diretório de export não existe: {export_dir}")
        return ExportBundle(
            export_dir=export_dir, result=result, source_map=SourceMap()
        )

    missing = [f for f in REQUIRED_FILES if not (export_dir / f).is_file()]
    for f in missing:
        result.add_error(f"arquivo obrigatório ausente no export: {f}")

    checksums_path = export_dir / "checksums.sha256"
    if checksums_path.is_file():
        issues = verify_checksums(export_dir, checksums_path)
        for issue in issues:
            result.add_error(issue)

    flat_objects: list[dict] = []
    if (export_dir / "flat-objects.json").is_file():
        try:
            flat_objects = read_json(export_dir / "flat-objects.json")
        except (ValueError, OSError) as exc:
            result.add_error(f"falha ao ler flat-objects.json: {exc}")

    text_index: dict = {}
    if (export_dir / "text-index.json").is_file():
        try:
            text_index = read_json(export_dir / "text-index.json")
        except (ValueError, OSError) as exc:
            result.add_error(f"falha ao ler text-index.json: {exc}")

    source_map = _build_source_map(export_dir, flat_objects, result)

    declaration_node_ids = [
        sf.node_id for sf in source_map.nodes_with_declaration()
    ]

    return ExportBundle(
        export_dir=export_dir,
        result=result,
        source_map=source_map,
        flat_objects=flat_objects,
        text_index=text_index,
        declaration_node_ids=declaration_node_ids,
    )


def _build_source_map(
    export_dir: Path, flat_objects: list[dict], result: ValidationResult
) -> SourceMap:
    """Constrói o SourceMap a partir de flat-objects.json, resolvendo os
    caminhos reais de declaration.st/implementation.st via metadata.json de
    cada objeto (mais robusto que reconstruir o nome do diretório
    `<node_id_seguro>__<nome_seguro>` manualmente)."""
    source_map = SourceMap()
    objects_root = export_dir / "objects"

    metadata_by_node_id: dict[str, tuple[Path, dict]] = {}
    if objects_root.is_dir():
        for obj_dir in sorted(objects_root.iterdir()):
            if not obj_dir.is_dir():
                continue
            metadata_path = obj_dir / "metadata.json"
            if not metadata_path.is_file():
                continue
            try:
                metadata = read_json(metadata_path)
            except (ValueError, OSError) as exc:
                result.add_error(
                    f"falha ao ler metadata.json em {obj_dir.name}: {exc}"
                )
                continue
            node_id = metadata.get("node_id")
            if node_id:
                metadata_by_node_id[node_id] = (obj_dir, metadata)

    for obj in flat_objects:
        node_id = obj.get("node_id")
        if not node_id:
            continue

        has_declaration = bool(obj.get("has_declaration"))
        has_implementation = bool(obj.get("has_implementation"))
        declaration_path: str | None = None
        implementation_path: str | None = None

        entry = metadata_by_node_id.get(node_id)
        if entry is not None:
            obj_dir, metadata = entry
            decl_meta = metadata.get("declaration") or {}
            impl_meta = metadata.get("implementation") or {}
            if decl_meta.get("available") and decl_meta.get("file"):
                decl_file = obj_dir / decl_meta["file"]
                if decl_file.is_file():
                    declaration_path = str(
                        decl_file.relative_to(export_dir)
                    ).replace("\\", "/")
                else:
                    result.add_warning(
                        f"metadata.json de {node_id} referencia "
                        f"declaration ausente em disco: {decl_file}"
                    )
            if impl_meta.get("available") and impl_meta.get("file"):
                impl_file = obj_dir / impl_meta["file"]
                if impl_file.is_file():
                    implementation_path = str(
                        impl_file.relative_to(export_dir)
                    ).replace("\\", "/")
                else:
                    result.add_warning(
                        f"metadata.json de {node_id} referencia "
                        f"implementation ausente em disco: {impl_file}"
                    )
        elif has_declaration or has_implementation:
            result.add_warning(
                f"objeto {node_id} indica has_declaration/has_implementation "
                "mas nenhum metadata.json correspondente foi encontrado em "
                "objects/"
            )

        source_map.add(
            SourceFile(
                node_id=node_id,
                name=obj.get("name"),
                type_guid=obj.get("type_guid"),
                object_guid=obj.get("object_guid"),
                declaration_path=declaration_path,
                implementation_path=implementation_path,
                has_declaration=has_declaration and declaration_path is not None,
                has_implementation=has_implementation
                and implementation_path is not None,
            )
        )

    return source_map


def build_static_index(export_dir: Path, output_dir: Path) -> dict:
    """Orquestra o pipeline completo desta fatia:

        load_export -> (para cada objeto com declaração) parse_declaration
        -> (se houver implementation.st) parse_implementation -> agrega
        PouSymbol/Call/Reference/Diagnostic -> escreve symbols.json /
        type-index.json / diagnostics.json / source-map.json / calls.json /
        references.json em `output_dir`.

    Decisão de projeto: esta função ESCREVE os artefatos em disco (em
    `output_dir`, que o chamador escolhe — sem timestamp hardcoded aqui) e
    também retorna um dict resumo em memória, para permanecer testável com
    `tmp_path` do pytest sem exigir leitura de disco de volta.

    Além dos 6 artefatos originais (symbols/type-index/diagnostics/
    source-map/calls/references), esta fatia (resolução de símbolos e
    análise read/write) também escreve resolved-calls.json, callers.json,
    resolved-references.json, read-write-index.json e
    resolution-diagnostics.json — este último SEPARADO de diagnostics.json
    (que continua só com diagnósticos de lexing/parsing). read-write-index
    .json é um artefato DISTINTO de resolved-references.json: agregado por
    símbolo (reads/writes/read_write), não uma lista plana por ocorrência.
    """
    output_dir = Path(output_dir)
    bundle = load_export(export_dir)

    all_diagnostics: list[Diagnostic] = []
    symbols: list[PouSymbol] = []
    all_calls: list[Call] = []
    all_references: list[Reference] = []
    all_type_symbols: list[TypeSymbol] = []

    for source_file in bundle.source_map.nodes_with_declaration():
        decl_path = bundle.export_dir / source_file.declaration_path
        try:
            text = decl_path.read_text(encoding="utf-8")
        except OSError as exc:
            all_diagnostics.append(
                Diagnostic(
                    severity="error",
                    code="declaration_file_read_error",
                    message=f"falha ao ler {decl_path}: {exc}",
                    location=None,
                    node_id=source_file.node_id,
                )
            )
            continue

        symbol, diags = parse_declaration(
            text, source_file.declaration_path, node_id=source_file.node_id
        )

        if symbol is None and any(
            d.code == "pou_header_not_found" for d in diags.diagnostics
        ):
            # Não é uma POU (PROGRAM/FUNCTION_BLOCK/FUNCTION) reconhecível —
            # tenta o caminho de GVL antes de desistir.
            gvl_symbol, gvl_diags = parse_gvl_declaration(
                text,
                source_file.declaration_path,
                node_id=source_file.node_id,
                gvl_name=source_file.name or source_file.node_id,
            )
            if gvl_symbol is not None:
                # GVL reconhecida: os diagnostics de "cabeçalho de POU não
                # encontrado" eram esperados para este caso e são
                # descartados em favor dos diagnostics da tentativa de GVL.
                symbol = gvl_symbol
                diags = gvl_diags
            elif any(
                d.code == "gvl_header_not_found" for d in gvl_diags.diagnostics
            ):
                # Nem POU nem GVL — tenta o 3o nível de fallback: DUT
                # (TYPE...END_TYPE). O nome do tipo vem do próprio conteúdo
                # do arquivo (ver dut_parser.parse_dut_declaration); o
                # parâmetro `type_name` só serve de identificação de
                # fallback caso o parser não consiga lê-lo do arquivo.
                type_symbol, dut_diags = parse_dut_declaration(
                    text,
                    source_file.declaration_path,
                    node_id=source_file.node_id,
                    type_name=source_file.name or source_file.node_id,
                )
                if type_symbol is not None:
                    # DUT reconhecido: descarta os diagnostics de POU/GVL
                    # (esperados para este caso) em favor dos diagnostics da
                    # tentativa de DUT.
                    diags = dut_diags
                    all_type_symbols.append(type_symbol)
                    symbol = None
                else:
                    # Nem POU, nem GVL, nem DUT — mantém os diagnostics
                    # originais de POU e agrega os de GVL/DUT para
                    # facilitar diagnóstico futuro.
                    diags.extend(gvl_diags)
                    diags.extend(dut_diags)
            else:
                # gvl_diags não trouxe "gvl_header_not_found" (situação
                # defensiva, não deveria ocorrer já que gvl_symbol é None
                # aqui) — preserva o comportamento anterior de apenas
                # agregar os diagnostics de GVL.
                diags.extend(gvl_diags)

        all_diagnostics.extend(diags.diagnostics)
        if symbol is not None:
            symbols.append(symbol)

        # implementation.st: parse de statements/chamadas (esta fatia).
        # Resolução de símbolo/classificação semântica continua fora de
        # escopo aqui — apenas o que é sintaticamente reconhecível.
        if source_file.has_implementation and source_file.implementation_path:
            impl_path = bundle.export_dir / source_file.implementation_path
            try:
                impl_text = impl_path.read_text(encoding="utf-8")
            except OSError as exc:
                all_diagnostics.append(
                    Diagnostic(
                        severity="warning",
                        code="implementation_file_read_error",
                        message=f"falha ao ler {impl_path}: {exc}",
                        location=None,
                        node_id=source_file.node_id,
                    )
                )
            else:
                _stmts, calls, references, impl_diags = parse_implementation(
                    impl_text,
                    source_file.implementation_path,
                    node_id=source_file.node_id,
                )
                all_calls.extend(calls)
                all_references.extend(references)
                all_diagnostics.extend(impl_diags.diagnostics)

    # Diagnósticos do próprio carregamento do export (checksum, arquivos
    # ausentes etc.) também entram no diagnostics.json final.
    for msg in bundle.result.errors:
        all_diagnostics.append(
            Diagnostic(severity="error", code="export_loader", message=msg)
        )
    for msg in bundle.result.warnings:
        all_diagnostics.append(
            Diagnostic(severity="warning", code="export_loader", message=msg)
        )

    symbols.sort(key=lambda s: s.node_id)
    all_calls.sort(
        key=lambda c: (
            c.node_id,
            c.location.line if c.location else 0,
            c.location.column if c.location else 0,
        )
    )
    all_references.sort(
        key=lambda r: (r.node_id, r.location.line, r.location.column)
    )
    all_type_symbols.sort(key=lambda t: t.node_id)

    declared_type_usage = _build_type_index(symbols)
    # `type-index.json` acumula duas chaves: `declared_type_usage` (o mapa
    # tipo-declarado -> localizações de uso, já existente antes desta fatia
    # sob a chave de topo `type_index`/arquivo type-index.json) e `types`
    # (os TypeSymbol de DUT extraídos nesta fatia). Decisão: uma única chave
    # nova dentro do JSON já existente, em vez de um arquivo separado —
    # confirmado que o único consumidor atual de type-index.json é o teste
    # de smoke de `test_export_loader.py` (que só verifica a EXISTÊNCIA do
    # arquivo na lista de artefatos) e a documentação (`docs/10-roadmap.md`,
    # `docs/PROJECT_CONTEXT_AND_ROADMAP.md`), nenhum dos quais depende do
    # formato interno — logo, livre para reestruturar sem quebrar consumidor
    # nenhum.
    type_index = {
        "declared_type_usage": declared_type_usage,
        "types": [t.to_dict() for t in all_type_symbols],
    }

    symbols_json = [s.to_dict() for s in symbols]
    diagnostics_json = [d.to_dict() for d in all_diagnostics]
    source_map_json = bundle.source_map.to_dict()
    calls_json = [c.to_dict() for c in all_calls]
    references_json = [r.to_dict() for r in all_references]
    type_symbols_json = type_index["types"]

    write_json(output_dir / "symbols.json", symbols_json)
    write_json(output_dir / "type-index.json", type_index)
    write_json(output_dir / "diagnostics.json", diagnostics_json)
    write_json(output_dir / "source-map.json", source_map_json)
    write_json(output_dir / "calls.json", calls_json)
    write_json(output_dir / "references.json", references_json)

    # --- Resolução de símbolos e análise read/write (fatia 3) -------------
    symbol_index = ProjectSymbolIndex(symbols, type_symbols=all_type_symbols)
    resolution_diags = DiagnosticsCollector()

    resolved_calls, call_diags = resolve_calls(all_calls, symbol_index)
    resolution_diags.extend(call_diags)

    resolved_references, ref_diags = resolve_references(
        all_references, symbol_index, resolved_calls
    )
    resolution_diags.extend(ref_diags)

    callers_index = build_callers_index(resolved_calls)
    read_write_index = build_read_write_index(resolved_references)

    resolved_calls_json = [rc.to_dict() for rc in resolved_calls]
    callers_json = callers_index
    resolved_references_json = [rr.to_dict() for rr in resolved_references]
    read_write_index_json = read_write_index
    resolution_diagnostics_json = resolution_diags.to_list()

    write_json(output_dir / "resolved-calls.json", resolved_calls_json)
    write_json(output_dir / "callers.json", callers_json)
    write_json(output_dir / "resolved-references.json", resolved_references_json)
    write_json(output_dir / "read-write-index.json", read_write_index_json)
    write_json(
        output_dir / "resolution-diagnostics.json", resolution_diagnostics_json
    )

    return {
        "symbols": symbols_json,
        "type_index": type_index,
        "type_symbols": type_symbols_json,
        "diagnostics": diagnostics_json,
        "source_map": source_map_json,
        "calls": calls_json,
        "references": references_json,
        "resolved_calls": resolved_calls_json,
        "callers": callers_json,
        "resolved_references": resolved_references_json,
        "read_write_index": read_write_index_json,
        "resolution_diagnostics": resolution_diagnostics_json,
        "result": bundle.result,
    }


def _build_type_index(symbols: list[PouSymbol]) -> dict[str, list[dict]]:
    """Mapa tipo declarado -> lista de localizações/symbol_ids que usam
    aquele tipo (busca futura tipo "quem usa TIME#")."""
    index: dict[str, list[dict]] = {}
    for symbol in symbols:
        for var in symbol.variables:
            type_key = var.declared_type
            entry = {
                "node_id": symbol.node_id,
                "pou_name": symbol.name,
                "variable_name": var.name,
                "location": var.location.to_dict() if var.location else None,
            }
            index.setdefault(type_key, []).append(entry)

    # Ordena para saída determinística.
    for entries in index.values():
        entries.sort(
            key=lambda e: (e["node_id"], e["variable_name"])
        )
    return dict(sorted(index.items()))

"""Análise OFFLINE (CPython, fora do MasterTool) do que `export_xml` produziu.

Separada do probe de propósito: interpretar XML dentro do IronPython
significaria decidir o formato no mesmo processo que o produziu, e qualquer
erro de parsing viraria erro dentro do MasterTool. Aqui o MasterTool já
fechou, os bytes estão congelados em disco e a análise não pode afetar nada.

O que este módulo faz: descobre o formato REAL do que apareceu. O que ele
**não** faz: interpretar lógica Ladder. A pergunta desta fase é "existe corpo
gráfico e em que formato", não "o que essa lógica faz".

Nenhuma dependência nova — `xml.etree.ElementTree` da biblioteca padrão. Os
arquivos vêm do MasterTool local, não da rede, mas o tamanho é limitado antes
do parse assim mesmo: um XML inesperadamente enorme travaria a validação por
consumo de memória, e "o exportador produziu algo gigante" é justamente um
resultado que interessa registrar, não sofrer.
"""

from __future__ import annotations

import hashlib
import json
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

# Versão do contrato DESTE artefato (análise offline do export PLCopen),
# inteiro. Constante própria: a análise evolui com o que o host consegue
# concluir sobre os bytes já congelados, independentemente do mapa estrutural
# e do modelo canônico. Ver `docs/19-contratos-de-execucao.md`, seção 7.
ANALYSIS_SCHEMA_VERSION = 1

# Teto de bytes por arquivo antes do parse. Acima disso o arquivo é
# registrado com `parse_skipped_too_large` em vez de parseado.
MAX_XML_PARSE_BYTES = 64 * 1024 * 1024

# Namespaces conhecidos do PLCopen XML. A detecção NUNCA é por prefixo (que
# é arbitrário no documento) — sempre pela URI.
PLCOPEN_NAMESPACE_MARKERS = (
    "http://www.plcopen.org/xml/tc6",
    "http://www.plcopen.org/xml/tc6_0200",
    "http://www.plcopen.org/xml/tc6_0201",
)

# Elementos estruturais procurados, sem prefixo (a comparação ignora o
# namespace, que é tratado à parte). Separados por papel para o inventário
# distinguir "há POUs" de "há corpo gráfico".
STRUCTURAL_ELEMENTS = ("project", "types", "pous", "pou", "body")
GRAPHICAL_BODY_ELEMENTS = ("LD", "FBD", "SFC")
GRAPHICAL_DETAIL_ELEMENTS = (
    "contact", "coil", "block", "inVariable", "outVariable",
    "connectionPointIn", "connectionPointOut",
)
TEXTUAL_BODY_ELEMENTS = ("ST", "IL")


class ExportAnalysisError(Exception):
    """Diretório de exportação inválido ou inacessível."""


@dataclass(frozen=True)
class XmlFileReport:
    relative_path: str
    size_bytes: int
    sha256: str
    is_xml: bool
    well_formed: bool
    parse_error: str | None = None
    root_tag: str | None = None
    namespaces: list[str] = field(default_factory=list)
    plcopen_detected: bool = False
    plcopen_version: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "relative_path": self.relative_path,
            "size_bytes": self.size_bytes,
            "sha256": self.sha256,
            "is_xml": self.is_xml,
            "well_formed": self.well_formed,
            "parse_error": self.parse_error,
            "root_tag": self.root_tag,
            "namespaces": self.namespaces,
            "plcopen_detected": self.plcopen_detected,
            "plcopen_version": self.plcopen_version,
        }


@dataclass(frozen=True)
class ExportAnalysis:
    export_root: Path
    xml_files: list[XmlFileReport]
    element_counts: dict
    target_match: dict
    result_case: str
    verdict: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": ANALYSIS_SCHEMA_VERSION,
            "export_root": str(self.export_root),
            "result_case": self.result_case,
            "verdict": self.verdict,
            "xml_file_count": len(self.xml_files),
            "element_counts": self.element_counts,
            "target_match": self.target_match,
        }


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def _local_name(tag: str) -> str:
    """Nome do elemento SEM namespace. `{uri}tag` -> `tag`."""
    if tag.startswith("{"):
        return tag.split("}", 1)[1]
    return tag


def _namespace_of(tag: str) -> str | None:
    if tag.startswith("{"):
        return tag[1:].split("}", 1)[0]
    return None


def _looks_like_xml(path: Path) -> bool:
    """Heurística de PRIMEIROS BYTES, não de extensão: a semântica de
    `stPath` era desconhecida, então o exportador pode ter produzido um nome
    sem `.xml`. Julgar por extensão faria a análise perder justamente o caso
    que motivou a guarda de diretório."""
    try:
        with open(path, "rb") as fh:
            head = fh.read(512)
    except OSError:
        return False
    stripped = head.lstrip(b"\xef\xbb\xbf \t\r\n")
    return stripped.startswith(b"<?xml") or stripped.startswith(b"<")


def _analyze_xml_file(path: Path, relative: str) -> tuple[XmlFileReport, Any]:
    size = path.stat().st_size
    digest = _sha256(path)
    is_xml = _looks_like_xml(path)

    if not is_xml:
        return XmlFileReport(relative, size, digest, False, False), None

    if size > MAX_XML_PARSE_BYTES:
        return (XmlFileReport(relative, size, digest, True, False,
                              parse_error="parse_skipped_too_large"), None)

    try:
        tree = ET.parse(str(path))
    except ET.ParseError as exc:
        return (XmlFileReport(relative, size, digest, True, False,
                              parse_error=str(exc)), None)
    except (OSError, ValueError) as exc:
        return (XmlFileReport(relative, size, digest, True, False,
                              parse_error=repr(exc)), None)

    root = tree.getroot()
    namespaces = sorted({
        ns for ns in (_namespace_of(el.tag) for el in root.iter())
        if ns is not None
    })
    plcopen = any(
        any(marker in ns for marker in PLCOPEN_NAMESPACE_MARKERS)
        for ns in namespaces
    )
    version = None
    for el in root.iter():
        if _local_name(el.tag) == "contentHeader":
            version = el.get("version") or version
        if _local_name(el.tag) == "fileHeader":
            version = el.get("contentDescription") or version

    return (XmlFileReport(relative, size, digest, True, True, None,
                          _local_name(root.tag), namespaces, plcopen, version),
            root)


def _count_elements(roots: list[Any]) -> dict:
    """Contagem por nome local, ignorando namespace. Um XML com prefixo
    diferente do esperado continua sendo contado — prefixo é escolha do
    documento, não do schema."""
    counts: dict[str, int] = {}
    for root in roots:
        if root is None:
            continue
        for el in root.iter():
            name = _local_name(el.tag)
            counts[name] = counts.get(name, 0) + 1

    def _subset(names):
        return {n: counts[n] for n in names if n in counts}

    return {
        "structural": _subset(STRUCTURAL_ELEMENTS),
        "graphical_bodies": _subset(GRAPHICAL_BODY_ELEMENTS),
        "graphical_details": _subset(GRAPHICAL_DETAIL_ELEMENTS),
        "textual_bodies": _subset(TEXTUAL_BODY_ELEMENTS),
        "all_element_names": sorted(counts),
    }


def _find_target(roots: list[Any], expected_name: str | None) -> dict:
    """Procura a POU alvo pelo atributo `name`, respeitando namespace no
    nome do elemento mas não no atributo (PLCopen usa atributos sem
    namespace)."""
    if not expected_name:
        return {"searched": False, "found": False,
                "reason": "expected_name não informado"}
    for root in roots:
        if root is None:
            continue
        for el in root.iter():
            if _local_name(el.tag) != "pou":
                continue
            if el.get("name") != expected_name:
                continue
            bodies = [
                _local_name(child.tag)
                for body in el.iter()
                if _local_name(body.tag) == "body"
                for child in body
            ]
            return {
                "searched": True,
                "found": True,
                "name": expected_name,
                "pou_type": el.get("pouType"),
                "body_kinds": sorted(set(bodies)),
                "has_graphical_body": any(
                    b in GRAPHICAL_BODY_ELEMENTS for b in bodies),
            }
    return {"searched": True, "found": False,
            "reason": "nenhum elemento <pou> com esse name no export"}


def classify_export_analysis(xml_files, element_counts, target_match) -> tuple[str, str]:
    """Casos P1/P2/P3/P4 — função pura, mesma disciplina dos probes."""
    parsed = [f for f in xml_files if f.well_formed]

    if not xml_files:
        return ("P3_no_output",
                "nenhum arquivo foi produzido em export-root. A chamada não "
                "gerou saída; nenhuma conclusão sobre o formato é possível.")

    if not parsed:
        return ("P4_unrecognized_format",
                "arquivos foram produzidos, mas nenhum é XML bem-formado. O "
                "formato precisa ser documentado antes de qualquer decisão "
                "sobre parser.")

    graphical = element_counts.get("graphical_bodies") or {}
    details = element_counts.get("graphical_details") or {}

    if graphical or details:
        return ("P1_graphical_body_present",
                "XML bem-formado com corpo gráfico presente (%s). Abre a fase "
                "de parser PLCopen — a lógica NÃO foi interpretada aqui."
                % ", ".join(sorted(set(list(graphical) + list(details)))))

    if any(f.plcopen_detected for f in parsed):
        return ("P2_declaration_only",
                "XML PLCopen bem-formado, mas SEM corpo gráfico. A exportação "
                "funciona; este alvo ou este escopo não inclui a implementação "
                "gráfica. Próximo passo: verificar se o escopo deve ser a "
                "Application em vez da POU isolada.")

    return ("P4_unrecognized_format",
            "XML bem-formado, mas sem namespace PLCopen reconhecido e sem "
            "corpo gráfico. Documentar o schema real antes de decidir o parser.")


def analyze_export_root(export_root: Path | str,
                        expected_name: str | None = None) -> ExportAnalysis:
    export_root = Path(export_root)
    if not export_root.is_dir():
        raise ExportAnalysisError(f"export-root inexistente: {export_root}")

    reports: list[XmlFileReport] = []
    roots: list[Any] = []
    for path in sorted(export_root.rglob("*")):
        # Reparse point NUNCA é seguido — mesma regra do probe. Um link
        # criado dentro do export-root poderia apontar para fora dele.
        if path.is_symlink():
            continue
        if not path.is_file():
            continue
        relative = str(path.relative_to(export_root)).replace("\\", "/")
        report, root = _analyze_xml_file(path, relative)
        reports.append(report)
        roots.append(root)

    element_counts = _count_elements(roots)
    target_match = _find_target(roots, expected_name)
    result_case, verdict = classify_export_analysis(
        reports, element_counts, target_match)

    return ExportAnalysis(export_root, reports, element_counts,
                          target_match, result_case, verdict)


def write_analysis(analysis: ExportAnalysis, output_dir: Path | str) -> list[Path]:
    """Grava os três artefatos host-side. NÃO toca em `export-root/` — os
    bytes produzidos pela API são preservados exatamente como saíram."""
    output_dir = Path(output_dir)
    written: list[Path] = []

    for name, payload in (
        ("xml-files.json", [f.to_dict() for f in analysis.xml_files]),
        ("xml-structure-inventory.json", analysis.element_counts),
        ("target-object-match.json", analysis.target_match),
        ("export-analysis.json", analysis.to_dict()),
    ):
        path = output_dir / name
        path.write_text(
            json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8")
        written.append(path)
    return written

"""Reaplica a classificação do probe 17 a uma execução JÁ ARQUIVADA.

Existe porque a coleta de 2026-07-27 foi válida mas a conclusão derivada
dela não: `dir()` devolveu lista vazia e o resultado foi classificado como
"caso B — evidência forte de que a superfície dinâmica não expõe Ladder".
Não é evidência de nada: `ladder_candidate_count` é derivado da lista do
`dir()`, então zero candidatos vindos de zero nomes enumerados mede ausência
de enumeração, não ausência de membros.

Reexecutar o MasterTool para corrigir isso seria desnecessário e pior:
trocaria uma coleta validada por outra, perdendo a comparabilidade. O defeito
está só na interpretação.

**Não reescreve nada coberto pelo `checksums.sha256` da coleta.** O
`manifest.json` e o `report.md` originais estão cobertos, então a revisão sai
em arquivos NOVOS (`classification-revision.json`/`.md`) — o par original
permanece byte a byte, e os checksums continuam fechando. Um artefato
arquivado que muda em silêncio deixa de ser evidência.

A regra de classificação NÃO é reimplementada aqui: é importada do próprio
probe (`classify_dynamic_probe_result`). Duas cópias divergiriam, e a
divergência apareceria como duas conclusões diferentes sobre a mesma coleta.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

# Versão do contrato DESTE artefato (reclassificação de resultado de probe),
# inteiro. Constante própria: a taxonomia de reclassificação evolui com o que
# se aprende sobre os canais sondados, sem relação com a versão do artefato
# original do probe (que é string, `"1.0"`, e permanece assim — famílias
# distintas, contratos distintos). Ver `docs/19-contratos-de-execucao.md`,
# seção 7.
RECLASSIFY_SCHEMA_VERSION = 1

REPO_ROOT = Path(__file__).resolve().parents[3]
PROBE_PATH = (REPO_ROOT / "scripts" / "mastertool" / "probes"
              / "17_probe_ladder_dynamic_surface.py")

REVISION_JSON_FILENAME = "classification-revision.json"
REVISION_MD_FILENAME = "classification-revision.md"

# Arquivos da COLETA — nunca reescritos por este módulo.
RAW_COLLECTION_FILENAMES = (
    "clr-members.json",
    "dynamic-dir-members.json",
    "dynamic-only-members.json",
    "shared-members.json",
    "whitelist-hasattr-results.json",
    "safe-getter-results.json",
    "ladder-candidate-members.json",
    "control-validation.json",
    "target-identity.json",
    "safety-declaration.json",
    "diagnostics.json",
)


class ReclassifyError(Exception):
    """Diretório de probe inválido ou incompleto."""


@dataclass(frozen=True)
class ClassificationRevision:
    probe_dir: Path
    original_result_case: str | None
    original_status: str | None
    revised_result_case: str
    revised_status: str
    verdict_message: str
    dynamic_named_access_validated: bool
    dynamic_enumeration_available: bool
    candidate_search_exhaustive: bool
    ladder_candidate_count: int
    dynamic_dir_member_count: int
    safe_getter_invocations: int
    changed: bool

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": RECLASSIFY_SCHEMA_VERSION,
            "revision_of": str(self.probe_dir),
            "original": {
                "result_case": self.original_result_case,
                "status": self.original_status,
            },
            "revised": {
                "result_case": self.revised_result_case,
                "status": self.revised_status,
                "verdict_message": self.verdict_message,
            },
            "capabilities": {
                "dynamic_named_access_validated": self.dynamic_named_access_validated,
                "dynamic_enumeration_available": self.dynamic_enumeration_available,
                "candidate_search_exhaustive": self.candidate_search_exhaustive,
            },
            "counts": {
                "ladder_candidate_count": self.ladder_candidate_count,
                "dynamic_dir_member_count": self.dynamic_dir_member_count,
                "safe_getter_invocations": self.safe_getter_invocations,
            },
            "changed": self.changed,
            "raw_collection_preserved": True,
            "note": (
                "Somente artefatos DERIVADOS de interpretação foram corrigidos. "
                "A coleta bruta e o checksums.sha256 original permanecem "
                "intocados; manifest.json e report.md originais não foram "
                "reescritos."
            ),
        }


def _load_probe_module():
    """Carrega o probe pelo caminho: o nome começa com dígito, então
    `import probes.17_...` é SyntaxError. Mesmo mecanismo já usado pelo
    runner e pelos testes."""
    import importlib.util

    spec = importlib.util.spec_from_file_location(
        "mastertool_bridge_probe_17_for_reclassify", str(PROBE_PATH))
    if spec is None or spec.loader is None:
        raise ReclassifyError(f"não foi possível carregar o probe 17: {PROBE_PATH}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _read_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise ReclassifyError(f"artefato ausente: {path.name}") from exc
    except ValueError as exc:
        raise ReclassifyError(f"artefato inválido (JSON): {path.name}") from exc


def reclassify_probe_dir(probe_dir: Path | str) -> ClassificationRevision:
    """Recalcula o caso a partir dos artefatos brutos. Nada é escrito aqui —
    quem escreve é `write_revision`, e só em arquivos novos."""
    probe_dir = Path(probe_dir)
    if not probe_dir.is_dir():
        raise ReclassifyError(f"diretório inexistente: {probe_dir}")

    control = _read_json(probe_dir / "control-validation.json")
    dir_members = _read_json(probe_dir / "dynamic-dir-members.json")
    candidates = _read_json(probe_dir / "ladder-candidate-members.json")
    safe_getters = _read_json(probe_dir / "safe-getter-results.json")

    # A coleta bruta é a fonte: o acesso por nome vale o que o controle
    # registrou, e a enumeração vale o que o dir() de fato produziu.
    named_access = bool(control.get("seen_by_dynamic_surface")) and not bool(
        control.get("seen_by_clr_reflection"))
    enumeration_available = len(dir_members) > 0

    probe = _load_probe_module()
    result_case, status, verdict = probe.classify_dynamic_probe_result(
        named_access, enumeration_available, len(candidates),
        len(dir_members), len(safe_getters))

    manifest_path = probe_dir / "manifest.json"
    original: dict[str, Any] = {}
    if manifest_path.is_file():
        original = _read_json(manifest_path)

    return ClassificationRevision(
        probe_dir=probe_dir,
        original_result_case=original.get("result_case"),
        original_status=original.get("status"),
        revised_result_case=result_case,
        revised_status=status,
        verdict_message=verdict,
        dynamic_named_access_validated=named_access,
        dynamic_enumeration_available=enumeration_available,
        candidate_search_exhaustive=enumeration_available,
        ladder_candidate_count=len(candidates),
        dynamic_dir_member_count=len(dir_members),
        safe_getter_invocations=len(safe_getters),
        changed=(original.get("result_case") != result_case
                 or original.get("status") != status),
    )


def _render_markdown(revision: ClassificationRevision) -> str:
    lines = [
        "# Revisão de classificação — probe 17",
        "",
        f"Diretório: `{revision.probe_dir.name}`",
        "",
        "A **coleta não foi refeita**. Os artefatos brutos e o "
        "`checksums.sha256` originais permanecem intocados; `manifest.json` e "
        "`report.md` originais **não** foram reescritos. Apenas a conclusão "
        "derivada deles é revisada aqui.",
        "",
        "## Classificação",
        "",
        "| | original | revisado |",
        "|---|---|---|",
        f"| `result_case` | `{revision.original_result_case}` | "
        f"**`{revision.revised_result_case}`** |",
        f"| `status` | `{revision.original_status}` | "
        f"**`{revision.revised_status}`** |",
        "",
        "## Capacidades, agora separadas",
        "",
        f"- `dynamic_named_access_validated`: **{revision.dynamic_named_access_validated}**",
        f"- `dynamic_enumeration_available`: **{revision.dynamic_enumeration_available}**",
        f"- `candidate_search_exhaustive`: **{revision.candidate_search_exhaustive}**",
        "",
        f"Contagens: {revision.ladder_candidate_count} candidato(s), "
        f"{revision.dynamic_dir_member_count} nome(s) enumerado(s), "
        f"{revision.safe_getter_invocations} getter(s) da whitelist testado(s).",
        "",
        "## Veredito revisado",
        "",
        revision.verdict_message,
        "",
    ]
    if revision.changed:
        lines += [
            "## Por que mudou",
            "",
            "Acesso por nome e enumeração de nomes são capacidades distintas e "
            "estavam compartilhando um único gate. Com o gate único, uma "
            "execução em que o controle foi confirmado por `hasattr()` "
            "(acesso funciona) mas o `dir()` voltou vazio (enumeração não "
            "funciona) era classificada como se a ausência de candidatos "
            "significasse algo — quando `ladder_candidate_count` é derivado "
            "justamente da lista vazia.",
            "",
        ]
    return "\n".join(lines)


def write_revision(revision: ClassificationRevision) -> tuple[Path, Path]:
    """Grava a revisão em arquivos NOVOS. Recusa sobrescrever qualquer
    arquivo da coleta bruta — a checagem é explícita e não depende de o
    chamador lembrar da regra."""
    json_path = revision.probe_dir / REVISION_JSON_FILENAME
    md_path = revision.probe_dir / REVISION_MD_FILENAME

    for path in (json_path, md_path):
        if path.name in RAW_COLLECTION_FILENAMES or path.name in (
                "manifest.json", "report.md", "checksums.sha256"):
            raise ReclassifyError(
                f"recusado: {path.name} pertence à coleta bruta e não pode ser "
                "reescrito por uma revisão de interpretação.")

    json_path.write_text(
        json.dumps(revision.to_dict(), indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8")
    md_path.write_text(_render_markdown(revision), encoding="utf-8")
    return json_path, md_path

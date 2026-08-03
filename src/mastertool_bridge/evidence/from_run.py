"""Empacota uma execução da fábrica num Evidence Bundle (fase R2).

Módulo puro: lê o que a execução deixou em disco e escreve o pacote. Não abre
o MasterTool, não recalcula nada que a execução já mediu e **não inventa
artefato ausente** — o que faltou entra como faltando, e o pacote fecha como
`sealed_incomplete`.

O MAPEAMENTO É LITERAL, E ESTÁ AQUI
===================================
A fábrica grava com nomes próprios (`execucao/`, `verificacao/`, `build/`), e
o layout do bundle é o de `ROADMAP` §2.7. A tradução entre os dois vive neste
módulo, num mapa explícito — não numa convenção de nome que "casa por acaso".
Um artefato novo da fábrica só entra no pacote quando alguém o acrescenta
aqui, o que é o comportamento certo: pacote é o que foi declarado, não o que
sobrou no diretório.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from mastertool_bridge.evidence.bundle import EvidenceBundle

SCHEMA_VERSION = 1

# (seção, nome no bundle) <- caminho relativo ao `artefatos/` da run.
#
# Lista literal: o que não está aqui não entra no pacote, mesmo existindo no
# diretório. Empacotar tudo que sobrou faria o hash do conjunto mudar por
# causa de arquivo temporário.
RUN_ARTIFACT_MAP = (
    ("plan", "normalized_plan.json", "authoring-plan.json"),
    ("execution", "mastertool_messages.json", "build/build-messages.json"),
    ("verification", "reopened_inventory.json",
     "verificacao/factory-verify-flat-nodes.json"),
    ("verification", "build_report.json", "build/build-completion.json"),
)


@dataclass
class PackagingResult:
    bundle_root: str | None = None
    status: str | None = None
    packaged: list[str] = field(default_factory=list)
    missing: list[str] = field(default_factory=list)
    problems: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.problems and self.status is not None

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": SCHEMA_VERSION,
            "ok": self.ok,
            "bundle_root": self.bundle_root,
            "status": self.status,
            "packaged": list(self.packaged),
            "missing": list(self.missing),
            "problems": list(self.problems),
        }


def _ler_json(caminho: Path) -> Any:
    try:
        return json.loads(caminho.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def package_run(run_dir: Path | str, bundle_root: Path | str, run_id: str,
                spec_path: Path | str | None = None,
                source_project_sha256: str | None = None,
                unexpected_changes: Any = None,
                rollback_spec: Any = None) -> PackagingResult:
    """Monta o pacote a partir de `<run>/artefatos/` e sela.

    Sela mesmo incompleto — a execução que deu errado é a que mais precisa
    ficar registrada, e um pacote sem manifesto é evidência solta.
    """
    resultado = PackagingResult()
    raiz_run = Path(run_dir)
    artefatos = raiz_run / "artefatos"
    if not artefatos.is_dir():
        resultado.problems.append(
            "run sem diretório `artefatos/`: %s" % artefatos)
        return resultado

    pacote = EvidenceBundle(bundle_root, run_id).create()
    resultado.bundle_root = str(pacote.root)

    conclusao = _ler_json(artefatos / "execucao" / "execution-completion.json")
    if not isinstance(conclusao, dict):
        resultado.problems.append(
            "execution-completion.json ausente ou ilegível — sem ele não há "
            "hash de plano nem de saída para registrar")
        conclusao = {}

    # --- source --------------------------------------------------------------
    if source_project_sha256:
        pacote.add("source", "project.sha256", source_project_sha256)
        resultado.packaged.append("source/project.sha256")
    else:
        resultado.missing.append("source/project.sha256")

    # --- plan ----------------------------------------------------------------
    if spec_path and Path(spec_path).is_file():
        pacote.add("plan", "specification.json",
                   Path(spec_path).read_bytes())
        resultado.packaged.append("plan/specification.json")
    else:
        resultado.missing.append("plan/specification.json")

    plan_sha = conclusao.get("plan_sha256")
    if isinstance(plan_sha, str) and plan_sha:
        pacote.add("plan", "plan.sha256", plan_sha)
        resultado.packaged.append("plan/plan.sha256")
    else:
        resultado.missing.append("plan/plan.sha256")

    # --- journal, do manifesto para JSONL -----------------------------------
    manifesto = _ler_json(artefatos / "execucao" / "execution-manifest.json")
    journal = manifesto.get("journal") if isinstance(manifesto, dict) else None
    if isinstance(journal, list):
        linhas = "".join(
            json.dumps(entrada, ensure_ascii=False, sort_keys=True) + "\n"
            for entrada in journal)
        pacote.add("execution", "journal.jsonl", linhas)
        resultado.packaged.append("execution/journal.jsonl")
    else:
        resultado.missing.append("execution/journal.jsonl")

    # --- o mapa literal ------------------------------------------------------
    for secao, nome_no_pacote, relativo in RUN_ARTIFACT_MAP:
        origem = artefatos / relativo
        if not origem.is_file():
            resultado.missing.append("%s/%s" % (secao, nome_no_pacote))
            continue
        pacote.add(secao, nome_no_pacote, origem.read_bytes())
        resultado.packaged.append("%s/%s" % (secao, nome_no_pacote))

    # --- o que mudou além do autorizado -------------------------------------
    if unexpected_changes is not None:
        pacote.add("verification", "unexpected_changes.json",
                   unexpected_changes)
        resultado.packaged.append("verification/unexpected_changes.json")
    else:
        resultado.missing.append("verification/unexpected_changes.json")

    # --- reversibilidade -----------------------------------------------------
    #
    # Condicional, e a condição vem do PLANO: um plano sem `modify:` não tem o
    # que reverter, e exigir o artefato dele faria toda execução de criação
    # selar incompleta. Um plano COM alteração e sem o texto anterior é um
    # pacote que registra uma mudança sem registrar como desfazê-la — e isso
    # entra como falta, não passa em silêncio.
    plano = _ler_json(artefatos / "authoring-plan.json")
    chaves = (plano.get("text_hashes") or {}) if isinstance(plano, dict) else {}
    tem_alteracao = any(isinstance(c, str) and c.startswith("modify:")
                        for c in chaves)
    # `exigidos_pelo_plano` vai para o SELO, e não só para a saída do comando.
    # Sem isso o pacote dizia `sealed_complete` com a seção `rollback/` vazia,
    # e a única pista era uma linha de texto que ninguém guarda.
    exigidos_pelo_plano: list[str] = []
    antes = artefatos / "execucao" / "before-texts.json"
    if antes.is_file():
        pacote.add("rollback", "before-texts.json", antes.read_bytes())
        resultado.packaged.append("rollback/before-texts.json")
    elif tem_alteracao:
        resultado.missing.append("rollback/before-texts.json")
        exigidos_pelo_plano.append("rollback/before-texts.json")

    if rollback_spec is not None:
        pacote.add("rollback", "rollback-spec.json", rollback_spec)
        resultado.packaged.append("rollback/rollback-spec.json")
    elif tem_alteracao:
        resultado.missing.append("rollback/rollback-spec.json")
        exigidos_pelo_plano.append("rollback/rollback-spec.json")

    # --- output --------------------------------------------------------------
    output_sha = conclusao.get("output_sha256")
    if isinstance(output_sha, str) and output_sha:
        pacote.add("output", "project.sha256", output_sha)
        resultado.packaged.append("output/project.sha256")
    else:
        resultado.missing.append("output/project.sha256")

    manifesto_selado = pacote.seal(metadata={
        "run_dir": str(raiz_run),
        "execution_status": conclusao.get("status"),
        "packaged_from": "run_project_factory.ps1",
        "plan_has_modifications": tem_alteracao,
    }, extra_missing=exigidos_pelo_plano)
    resultado.status = manifesto_selado.status
    return resultado

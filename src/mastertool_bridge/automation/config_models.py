"""Modelo e validação de `run-config.json` (Etapa B, seção 2 do contrato
`docs/16-supervised-runner-contract.md`).

Este módulo roda no lado HOST (Python 3.11, fora do MasterTool). Ele é o
lado que ESCREVE `run-config.json`; quem lê é o runner interno IronPython
2.7 (`scripts/mastertool/automation/`, fora de escopo deste módulo).

Fail-closed deliberado: `RunOperations` rejeita, na construção, qualquer
operação da lista proibida (`build`, `save`, `online`, `download`, `force`)
que venha `True`, e qualquer chave desconhecida em `operations`. Isto é
defesa em profundidade do lado host — o runner interno também rejeita (via
`common/safety.py`, fora de escopo aqui), mas um `run-config.json` inválido
não deve nem chegar a ser escrito em disco.
"""

from __future__ import annotations

from dataclasses import dataclass, field

SCHEMA_VERSION = 1

# Chaves conhecidas de `operations`. Qualquer chave fora deste conjunto
# reprova a validação (fail-closed: uma operação desconhecida não pode ser
# silenciosamente ignorada nem silenciosamente aceita).
KNOWN_OPERATION_KEYS = frozenset({
    "scan_project_tree",
    "export_text",
    "inventory_graphic_objects",
    "probe_ladder_surface",
    "build",
    "save",
    "online",
    "download",
    "force",
})

# Operações que o runner interno NUNCA pode receber como True (seção 3 do
# contrato). `download`/`force` não aparecem no exemplo da seção 2, mas a
# seção 3 as cita explicitamente na lista proibida.
FORBIDDEN_OPERATION_KEYS = frozenset({"build", "save", "online", "download", "force"})


class ConfigValidationError(ValueError):
    """`run-config.json` inválido — nunca deve ser escrito em disco."""


@dataclass(frozen=True)
class RunOperations:
    """Seção `operations` de `run-config.json`.

    `to_dict()` só inclui as chaves explicitamente fornecidas em
    `extra_keys` mais as três conhecidas e permitidas
    (`scan_project_tree`/`export_text`/`inventory_graphic_objects`), para
    não inventar chaves não pedidas pelo chamador."""

    scan_project_tree: bool = True
    export_text: bool = True
    inventory_graphic_objects: bool = False
    probe_ladder_surface: bool = False
    build: bool = False
    save: bool = False
    online: bool = False
    extra: dict = field(default_factory=dict)

    def __post_init__(self) -> None:
        all_keys = set(self.extra.keys())
        unknown = all_keys - KNOWN_OPERATION_KEYS
        if unknown:
            raise ConfigValidationError(
                "operations contém chave(s) desconhecida(s), fail-closed: "
                + ", ".join(sorted(unknown)))

        merged = self.to_dict()
        forbidden_true = [
            key for key in FORBIDDEN_OPERATION_KEYS
            if merged.get(key) is True
        ]
        if forbidden_true:
            raise ConfigValidationError(
                "operations proíbe estas chaves como True: "
                + ", ".join(sorted(forbidden_true)))

    def to_dict(self) -> dict:
        merged = {
            "scan_project_tree": self.scan_project_tree,
            "export_text": self.export_text,
            "inventory_graphic_objects": self.inventory_graphic_objects,
            "probe_ladder_surface": self.probe_ladder_surface,
            "build": self.build,
            "save": self.save,
            "online": self.online,
        }
        merged.update(self.extra)
        return merged


@dataclass(frozen=True)
class LadderProbeConfig:
    """Seção `ladder_probe` de `run-config.json` (contrato, seção 3.1 —
    Fase L1). Obrigatória quando `operations.probe_ladder_surface` é
    `True`; ausente quando desligada. Os quatro campos são exigidos JUNTOS
    (nenhum é redundante — ver seção 3.1 do contrato) e nenhum deles pode
    ser hardcoded em código: vêm sempre do config, mesma regra dos
    `expected_application_*` (seção 6.3 do contrato)."""

    target_node_id: str
    expected_name: str
    expected_guid: str
    expected_type_guid: str

    def __post_init__(self) -> None:
        required_strings = {
            "target_node_id": self.target_node_id,
            "expected_name": self.expected_name,
            "expected_guid": self.expected_guid,
            "expected_type_guid": self.expected_type_guid,
        }
        missing = [name for name, value in required_strings.items() if not value]
        if missing:
            raise ConfigValidationError(
                "ladder_probe com campo(s) obrigatório(s) vazio(s): "
                + ", ".join(missing))

    def to_dict(self) -> dict:
        return {
            "target_node_id": self.target_node_id,
            "expected_name": self.expected_name,
            "expected_guid": self.expected_guid,
            "expected_type_guid": self.expected_type_guid,
        }


@dataclass(frozen=True)
class RunConfig:
    """Corresponde EXATAMENTE às chaves da seção 2 do contrato (mais a seção
    `ladder_probe` opcional da seção 3.1). Nenhum campo extra, nenhum campo
    faltando — o runner interno espera este schema."""

    run_id: str
    mode: str
    repo_root: str
    mastertool_scripts_dir: str
    expected_project_path: str
    expected_project_sha256: str
    expected_application_name: str
    expected_application_guid: str
    expected_application_type_guid: str
    run_dir: str
    output_dir: str
    allowed_output_root: str
    operations: RunOperations
    ladder_probe: LadderProbeConfig | None = None
    schema_version: int = SCHEMA_VERSION

    def __post_init__(self) -> None:
        required_strings = {
            "run_id": self.run_id,
            "mode": self.mode,
            "repo_root": self.repo_root,
            "mastertool_scripts_dir": self.mastertool_scripts_dir,
            "expected_project_path": self.expected_project_path,
            "expected_project_sha256": self.expected_project_sha256,
            "expected_application_name": self.expected_application_name,
            "expected_application_guid": self.expected_application_guid,
            "expected_application_type_guid": self.expected_application_type_guid,
            "run_dir": self.run_dir,
            "output_dir": self.output_dir,
            "allowed_output_root": self.allowed_output_root,
        }
        missing = [name for name, value in required_strings.items() if not value]
        if missing:
            raise ConfigValidationError(
                "run-config.json com campo(s) obrigatório(s) vazio(s): "
                + ", ".join(missing))
        if not isinstance(self.operations, RunOperations):
            raise ConfigValidationError(
                "operations deve ser RunOperations (já validada); "
                "não construa run-config.json com um dict cru.")
        if self.ladder_probe is not None and not isinstance(self.ladder_probe, LadderProbeConfig):
            raise ConfigValidationError(
                "ladder_probe deve ser LadderProbeConfig (já validada); "
                "não construa run-config.json com um dict cru.")

        # Coerência nas duas direções (contrato, seção 3.1): operação ligada
        # sem a seção -> reprova; seção presente com a operação desligada ->
        # também reprova (config incoerente não é aceito por omissão).
        if self.operations.probe_ladder_surface and self.ladder_probe is None:
            raise ConfigValidationError(
                "operations.probe_ladder_surface=True exige a seção "
                "ladder_probe, que está ausente.")
        if self.ladder_probe is not None and not self.operations.probe_ladder_surface:
            raise ConfigValidationError(
                "ladder_probe presente mas operations.probe_ladder_surface="
                "False — configuração incoerente, fail-closed.")

    def to_dict(self) -> dict:
        """Produz EXATAMENTE as chaves da seção 2 do contrato — nomes e
        aninhamento, sem campos extras. A seção `ladder_probe` só aparece
        quando existir (nunca emite `null`)."""
        data = {
            "schema_version": self.schema_version,
            "run_id": self.run_id,
            "mode": self.mode,
            "repo_root": self.repo_root,
            "mastertool_scripts_dir": self.mastertool_scripts_dir,
            "expected_project_path": self.expected_project_path,
            "expected_project_sha256": self.expected_project_sha256,
            "expected_application_name": self.expected_application_name,
            "expected_application_guid": self.expected_application_guid,
            "expected_application_type_guid": self.expected_application_type_guid,
            "run_dir": self.run_dir,
            "output_dir": self.output_dir,
            "allowed_output_root": self.allowed_output_root,
            "operations": self.operations.to_dict(),
        }
        if self.ladder_probe is not None:
            data["ladder_probe"] = self.ladder_probe.to_dict()
        return data

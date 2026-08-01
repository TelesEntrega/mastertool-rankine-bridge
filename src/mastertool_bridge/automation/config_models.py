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
    "probe_ladder_dynamic_surface",
    "probe_ladder_extender_surface",
    "probe_plcopen_export_signature",
    "export_plcopen_xml",
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
    probe_ladder_dynamic_surface: bool = False
    probe_ladder_extender_surface: bool = False
    probe_plcopen_export_signature: bool = False
    export_plcopen_xml: bool = False
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
            "probe_ladder_dynamic_surface": self.probe_ladder_dynamic_surface,
            "probe_ladder_extender_surface": self.probe_ladder_extender_surface,
            "probe_plcopen_export_signature": self.probe_plcopen_export_signature,
            "export_plcopen_xml": self.export_plcopen_xml,
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
class PlcopenExportSignatureProbeConfig:
    """Seção `plcopen_export_signature_probe`. Mesmos quatro campos de
    identidade dos probes Ladder MAIS `inspect_active_application` — por
    isso não reutiliza `LadderProbeConfig`, que valida exatamente quatro
    strings. Um quinto campo aceito e silenciosamente ignorado seria o mesmo
    defeito que `KNOWN_OPERATION_KEYS` existe para impedir."""

    target_node_id: str
    expected_name: str
    expected_guid: str
    expected_type_guid: str
    inspect_active_application: bool = True

    def __post_init__(self) -> None:
        required = {
            "target_node_id": self.target_node_id,
            "expected_name": self.expected_name,
            "expected_guid": self.expected_guid,
            "expected_type_guid": self.expected_type_guid,
        }
        missing = [name for name, value in required.items() if not value]
        if missing:
            raise ConfigValidationError(
                "plcopen_export_signature_probe com campo(s) obrigatório(s) vazio(s): "
                + ", ".join(missing))
        # Booleano ESTRITO: 0/1/"true" fariam a config parecer válida com um
        # valor que não expressa a intenção.
        if not isinstance(self.inspect_active_application, bool):
            raise ConfigValidationError(
                "plcopen_export_signature_probe.inspect_active_application deve ser "
                f"booleano true/false (recebido: {self.inspect_active_application!r})")

    def to_dict(self) -> dict:
        return {
            "target_node_id": self.target_node_id,
            "expected_name": self.expected_name,
            "expected_guid": self.expected_guid,
            "expected_type_guid": self.expected_type_guid,
            "inspect_active_application": self.inspect_active_application,
        }


@dataclass(frozen=True)
class PlcopenExportConfig:
    """Seção `plcopen_export`. Os três booleanos existem para AUDITORIA — um
    `run-config.json` arquivado precisa dizer com que argumentos a exportação
    correu — e **não** para abrir matriz de execução: qualquer valor
    diferente de `False` reprova. Uma combinação nunca testada não pode
    entrar em produção por alguém editar o JSON."""

    target_node_id: str
    expected_name: str
    expected_guid: str
    expected_type_guid: str
    target_leaf_name: str
    recursive: bool = False
    export_folder_structure: bool = False
    plain_text: bool = False

    def __post_init__(self) -> None:
        required = {
            "target_node_id": self.target_node_id,
            "expected_name": self.expected_name,
            "expected_guid": self.expected_guid,
            "expected_type_guid": self.expected_type_guid,
            "target_leaf_name": self.target_leaf_name,
        }
        missing = [name for name, value in required.items() if not value]
        if missing:
            raise ConfigValidationError(
                "plcopen_export com campo(s) obrigatório(s) vazio(s): "
                + ", ".join(missing))

        # `target_leaf_name` é nome SIMPLES. A travessia é barrada aqui, no
        # host, além de no probe: o caminho mais barato de recusar é o que
        # nunca chega perto do MasterTool.
        leaf = self.target_leaf_name
        if ("/" in leaf or "\\" in leaf or leaf in (".", "..")
                or ":" in leaf or leaf.startswith("~")):
            raise ConfigValidationError(
                f"plcopen_export.target_leaf_name deve ser um nome simples, sem "
                f"separador, drive ou '..' (recebido: {leaf!r})")

        for name in ("recursive", "export_folder_structure", "plain_text"):
            value = getattr(self, name)
            if value is not False:
                raise ConfigValidationError(
                    f"plcopen_export.{name} deve ser exatamente False nesta versão "
                    f"(recebido: {value!r}) — os três booleanos são de auditoria, "
                    "não abrem matriz de execução.")

    def to_dict(self) -> dict:
        return {
            "target_node_id": self.target_node_id,
            "expected_name": self.expected_name,
            "expected_guid": self.expected_guid,
            "expected_type_guid": self.expected_type_guid,
            "recursive": self.recursive,
            "export_folder_structure": self.export_folder_structure,
            "plain_text": self.plain_text,
            "target_leaf_name": self.target_leaf_name,
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
    # Seção INDEPENDENTE de `ladder_probe` (probe 17, contrato seção 3.1):
    # reutiliza a mesma dataclass `LadderProbeConfig` (mesmos 4 campos
    # obrigatórios) porque a identidade de alvo é o mesmo formato — mas é
    # uma seção própria, ligada por uma flag própria, para poder ser
    # habilitada separadamente do probe 16.
    ladder_dynamic_probe: LadderProbeConfig | None = None
    ladder_extender_probe: LadderProbeConfig | None = None
    plcopen_export_signature_probe: PlcopenExportSignatureProbeConfig | None = None
    plcopen_export: PlcopenExportConfig | None = None
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
        if self.ladder_dynamic_probe is not None and not isinstance(
                self.ladder_dynamic_probe, LadderProbeConfig):
            raise ConfigValidationError(
                "ladder_dynamic_probe deve ser LadderProbeConfig (já "
                "validada); não construa run-config.json com um dict cru.")

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

        # Mesma regra, seção independente do probe 17.
        if self.operations.probe_ladder_dynamic_surface and self.ladder_dynamic_probe is None:
            raise ConfigValidationError(
                "operations.probe_ladder_dynamic_surface=True exige a seção "
                "ladder_dynamic_probe, que está ausente.")
        if self.ladder_dynamic_probe is not None and not self.operations.probe_ladder_dynamic_surface:
            raise ConfigValidationError(
                "ladder_dynamic_probe presente mas "
                "operations.probe_ladder_dynamic_surface=False — "
                "configuração incoerente, fail-closed.")

        # Mesma regra, seção independente do probe 18.
        if self.operations.probe_ladder_extender_surface and self.ladder_extender_probe is None:
            raise ConfigValidationError(
                "operations.probe_ladder_extender_surface=True exige a seção "
                "ladder_extender_probe, que está ausente.")
        if self.ladder_extender_probe is not None and not self.operations.probe_ladder_extender_surface:
            raise ConfigValidationError(
                "ladder_extender_probe presente mas "
                "operations.probe_ladder_extender_surface=False — "
                "configuração incoerente, fail-closed.")

        # Mesma regra, seção independente do probe 19.
        if (self.operations.probe_plcopen_export_signature
                and self.plcopen_export_signature_probe is None):
            raise ConfigValidationError(
                "operations.probe_plcopen_export_signature=True exige a seção "
                "plcopen_export_signature_probe, que está ausente.")
        if (self.plcopen_export_signature_probe is not None
                and not self.operations.probe_plcopen_export_signature):
            raise ConfigValidationError(
                "plcopen_export_signature_probe presente mas "
                "operations.probe_plcopen_export_signature=False — "
                "configuração incoerente, fail-closed.")

        # Mesma regra, seção independente da exportação.
        if self.operations.export_plcopen_xml and self.plcopen_export is None:
            raise ConfigValidationError(
                "operations.export_plcopen_xml=True exige a seção plcopen_export, "
                "que está ausente.")
        if self.plcopen_export is not None and not self.operations.export_plcopen_xml:
            raise ConfigValidationError(
                "plcopen_export presente mas operations.export_plcopen_xml=False — "
                "configuração incoerente, fail-closed.")

        # As cinco operações de investigação sobre o MESMO objeto.
        # Combiná-los numa run produziria vereditos concorrentes sob um único
        # status — ambiguidade justamente no registro de auditoria. O host
        # recusa cedo, antes de gerar o `run-config.json`, para o operador não
        # descobrir isso só quando o runner interno reprovar.
        enabled_probes = [
            name for name, on in (
                ("probe_ladder_surface", self.operations.probe_ladder_surface),
                ("probe_ladder_dynamic_surface", self.operations.probe_ladder_dynamic_surface),
                ("probe_ladder_extender_surface", self.operations.probe_ladder_extender_surface),
                ("probe_plcopen_export_signature",
                 self.operations.probe_plcopen_export_signature),
                ("export_plcopen_xml", self.operations.export_plcopen_xml),
            ) if on
        ]
        if len(enabled_probes) > 1:
            raise ConfigValidationError(
                "mais de um probe Ladder ligado na mesma run: "
                + ", ".join(sorted(enabled_probes))
                + ". Cada probe investiga um canal distinto e tem gate de "
                "validade próprio; rode um por vez.")

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
        if self.ladder_dynamic_probe is not None:
            data["ladder_dynamic_probe"] = self.ladder_dynamic_probe.to_dict()
        if self.ladder_extender_probe is not None:
            data["ladder_extender_probe"] = self.ladder_extender_probe.to_dict()
        if self.plcopen_export_signature_probe is not None:
            data["plcopen_export_signature_probe"] = self.plcopen_export_signature_probe.to_dict()
        if self.plcopen_export is not None:
            data["plcopen_export"] = self.plcopen_export.to_dict()
        return data

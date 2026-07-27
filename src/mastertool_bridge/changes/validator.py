"""Validação de change sets contra a política de segurança (fail closed)."""

from __future__ import annotations

from mastertool_bridge.models import ChangeSet, ValidationResult


def validate_change_set_policy(change_set: ChangeSet) -> ValidationResult:
    result = ValidationResult(subject=f"change set {change_set.change_id}")
    checks = change_set.safety_checks

    if checks.get("requires_human_approval") is not True:
        result.add_error(
            "safety_checks.requires_human_approval deve ser true — aprovação "
            "humana é obrigatória para qualquer alteração.")

    if change_set.highest_risk == "critical":
        result.add_error(
            "Change set contém objeto de risco CRÍTICO: aplicação automática "
            "é proibida pela política. Requer processo manual com avaliação "
            "de risco documentada e aprovação sênior.")

    if checks.get("changes_physical_outputs"):
        critical = [o.qualified_name for o in change_set.objects
                    if o.risk_level != "critical"]
        if critical:
            result.add_error(
                "changes_physical_outputs=true exige risk_level=critical em "
                f"todos os objetos; em desacordo: {', '.join(critical)}")

    if checks.get("changes_hardware_configuration"):
        result.add_error(
            "Alteração de configuração de hardware é proibida "
            "(config/safety-policy.yaml: forbidden_operations).")

    if checks.get("changes_retain_data") and change_set.highest_risk in ("low", "medium"):
        result.add_error(
            "changes_retain_data=true exige risco mínimo 'high' nos objetos "
            "afetados (dados RETAIN/PERSISTENT).")

    if not checks.get("requires_compile", False):
        result.add_error(
            "requires_compile deve ser true: toda importação futura exige "
            "compilação bem-sucedida antes da aprovação.")

    if change_set.status in ("approved", "applied") and not change_set.source_export_hash:
        result.add_error(
            f"status '{change_set.status}' exige source_export_hash preenchido "
            "(validação de origem).")

    if change_set.status == "applied":
        result.add_error(
            "status 'applied' não é aceito nesta fase: importação está "
            "desabilitada até as fases 0-3 serem aprovadas.")
    return result

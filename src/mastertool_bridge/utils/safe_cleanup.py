"""Remoção segura e auditada de diretórios de artefatos de execução.

Motivo (2026-07-23): um `rm -rf` com glob por sufixo apagou por engano os
artefatos reais de uma execução no MasterTool durante a limpeza de um
dry-run separado. Este módulo formaliza as proteções que deveriam ter
impedido isso — usado por `scripts/maintenance/safe_clean_artifact.py`.

Nenhuma proteção aqui é opcional: `validate_target` levanta
`UnsafeCleanupError` na primeira violação encontrada, sem tentar "corrigir"
o caminho fornecido.
"""

from __future__ import annotations

from pathlib import Path

# Deve bater com scripts/mastertool/common/file_io.py: SENTINEL_FILENAME —
# gravado por new_export_dir() em todo diretório criado por esta ferramenta.
SENTINEL_FILENAME = ".mastertool-bridge-run"

# Nome da pasta raiz de artefatos gerados (workspace/) — o alvo de remoção
# deve estar DENTRO dela, nunca fora, e nunca ser ela mesma nem uma de suas
# subpastas de primeiro nível (workspace/logs, workspace/exports, ...).
WORKSPACE_DIR_NAME = "workspace"


class UnsafeCleanupError(Exception):
    """Levantada quando um caminho-alvo não passa em alguma proteção
    obrigatória de segurança. A mensagem explica exatamente qual."""


def _find_workspace_root(start: Path) -> Path | None:
    for candidate in (start, *start.parents):
        if candidate.name == WORKSPACE_DIR_NAME:
            return candidate
    return None


def validate_target(target: str) -> Path:
    """Valida um caminho-alvo de remoção. Retorna o Path validado ou
    levanta UnsafeCleanupError. Nunca toca o sistema de arquivos para
    "corrigir" o caminho — só lê, para verificar.
    """
    if not target:
        raise UnsafeCleanupError("Caminho vazio: recusado.")

    if "*" in target or "?" in target:
        raise UnsafeCleanupError(
            "Caminho contém curinga ('*' ou '?'): recusado. Este utilitário "
            "nunca aceita glob — informe o caminho exato de um único diretório.")

    path = Path(target)
    if not path.is_absolute():
        raise UnsafeCleanupError(
            "Caminho não é absoluto: recusado. Forneça o caminho absoluto completo.")

    if not path.exists():
        raise UnsafeCleanupError(
            "Caminho não existe: recusado (nada a remover; evita validar um "
            "alvo hipotético que poderia, no futuro, casar com outra coisa).")

    if not path.is_dir():
        raise UnsafeCleanupError("Caminho não é um diretório: recusado.")

    workspace_root = _find_workspace_root(path)
    if workspace_root is None:
        raise UnsafeCleanupError(
            f"Caminho não está dentro de uma pasta '{WORKSPACE_DIR_NAME}/': recusado.")

    if path == workspace_root:
        raise UnsafeCleanupError(
            f"Alvo é a própria pasta '{WORKSPACE_DIR_NAME}/': recusado.")

    rel_parts = path.relative_to(workspace_root).parts
    if len(rel_parts) < 2:
        raise UnsafeCleanupError(
            f"Alvo é uma subpasta de primeiro nível de '{WORKSPACE_DIR_NAME}/' "
            f"(ex.: '{WORKSPACE_DIR_NAME}/logs' inteiro) — recusado. O alvo "
            "deve ser um diretório de execução específico, não a categoria inteira.")

    sentinel = path / SENTINEL_FILENAME
    if not sentinel.is_file():
        raise UnsafeCleanupError(
            f"Arquivo sentinela '{SENTINEL_FILENAME}' não encontrado no "
            "diretório alvo — recusado. Só diretórios criados por esta "
            "ferramenta (common/file_io.new_export_dir) podem ser removidos "
            "por este utilitário.")

    return path


def list_files(path: Path) -> list[Path]:
    """Lista (ordenada) de todos os arquivos dentro de `path`, recursivamente."""
    return sorted(p for p in path.rglob("*") if p.is_file())

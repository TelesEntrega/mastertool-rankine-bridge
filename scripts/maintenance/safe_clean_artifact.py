#!/usr/bin/env python3
"""Remoção segura e auditada de UM diretório de artefato de execução
(ex.: workspace/logs/<timestamp>_<script>/).

Motivo (2026-07-23): um `rm -rf` com glob por sufixo apagou por engano os
artefatos reais de uma execução real no MasterTool durante a limpeza de um
dry-run separado. Este utilitário existe para que isso não se repita —
ver `src/mastertool_bridge/utils/safe_cleanup.py` para as proteções.

Proteções obrigatórias (todas ativas, nenhuma opcional):
  - recusa qualquer glob ('*'/'?') no caminho;
  - recusa caminho vazio;
  - exige caminho ABSOLUTO;
  - exige diretório EXISTENTE de verdade (não um padrão);
  - exige que o alvo esteja dentro de workspace/, nunca fora;
  - recusa remover workspace/ inteiro ou uma subpasta de 1º nível
    (ex.: workspace/logs inteiro) — o alvo deve ser um diretório de
    execução específico;
  - exige o arquivo sentinela `.mastertool-bridge-run` (gravado por
    common/file_io.new_export_dir ao criar o diretório);
  - modo dry-run é o PADRÃO — só remove de fato com --confirm explícito;
  - lista todos os arquivos antes de remover (dry-run ou não).

Uso:
    python scripts/maintenance/safe_clean_artifact.py <caminho-absoluto>
    python scripts/maintenance/safe_clean_artifact.py <caminho-absoluto> --confirm
"""

import argparse
import shutil
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(REPO_ROOT / "src"))

from mastertool_bridge.utils.safe_cleanup import (  # noqa: E402
    UnsafeCleanupError, list_files, validate_target)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("target", help="Caminho ABSOLUTO do diretório a remover")
    parser.add_argument("--confirm", action="store_true",
                        help="Confirma a remoção de fato (sem isso, é só dry-run)")
    args = parser.parse_args()

    try:
        target = validate_target(args.target)
    except UnsafeCleanupError as exc:
        print(f"[BLOQUEADO] {exc}", file=sys.stderr)
        return 1

    files = list_files(target)
    print(f"Alvo validado: {target}")
    print(f"Arquivo(s) que seriam removidos ({len(files)}):")
    for f in files:
        print(f"  - {f}")

    if not args.confirm:
        print("\n[DRY-RUN] Nenhum arquivo foi removido. Rode novamente com "
             "--confirm para remover de fato.")
        return 0

    shutil.rmtree(target)
    print(f"\n[OK] Removido: {target}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

#!/usr/bin/env python3
"""Emite o plano de autoria a partir de uma `project_spec`. HOST, 100% offline.

Este arquivo é a única ponte entre o `mastertool_bridge.planner` (CPython 3) e
o host PowerShell. Ele não abre o MasterTool, não importa IronPython e não toca
em projeto nenhum: lê JSON, chama `build_authoring_plan`, grava JSON.

Por que existe um script em vez de o wrapper chamar `python -c`: um `-c` de
uma linha esconde o código que decide se a spec vira plano, e esse código é
exatamente o que precisa ser revisável. Aqui ele tem arquivo, teste e diff.

CÓDIGO DE SAÍDA:

    0   plano emitido E executável
    2   spec inválida (problemas do validador), nenhum plano gravado
    3   plano emitido e NÃO executável (lacuna de medição) -- o arquivo é
        gravado assim mesmo, porque um plano com lacuna é evidência do que
        falta medir, e apagá-lo apagaria a explicação

A distinção entre 2 e 3 importa: uma pede corrigir a spec, a outra pede medir
uma operação contra o produto. Um código só faria as duas parecerem a mesma
coisa.
"""

from __future__ import annotations

import argparse
import json
import os
import sys

_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
_SRC = os.path.join(_REPO_ROOT, "src")
if _SRC not in sys.path:
    sys.path.insert(0, _SRC)

from mastertool_bridge.planner.planner import build_authoring_plan  # noqa: E402

EXIT_OK = 0
EXIT_SPEC_INVALID = 2
EXIT_PLAN_NOT_EXECUTABLE = 3


def _write_json_no_bom(path: str, payload: object) -> None:
    """UTF-8 sem BOM, sempre.

    `Out-File -Encoding utf8` do PowerShell 5.1 grava BOM e o artefato fica
    ilegível para leitor JSON estrito -- achado real da run-008. Aqui o mesmo
    cuidado, do lado do Python: `encoding="utf-8"` nunca escreve BOM, e é isso
    que este comentário existe para fixar.
    """
    directory = os.path.dirname(os.path.abspath(path))
    if directory and not os.path.isdir(directory):
        os.makedirs(directory)
    with open(path, "w", encoding="utf-8", newline="\n") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2, sort_keys=True)
        handle.write("\n")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="project_spec -> plano de autoria (offline)")
    parser.add_argument("--spec", required=True)
    parser.add_argument("--out", required=True)
    args = parser.parse_args(argv)

    try:
        with open(args.spec, encoding="utf-8") as handle:
            spec = json.load(handle)
    except (OSError, ValueError) as exc:
        print(f"[BLOQUEADO] spec ilegível: {exc!r}")
        return EXIT_SPEC_INVALID

    result = build_authoring_plan(spec)
    if result.problems:
        print(f"[BLOQUEADO] a spec tem {len(result.problems)} problema(s):")
        for problem in result.problems:
            print(f"  - {problem}")
        print("Nenhum plano foi gravado.")
        return EXIT_SPEC_INVALID

    plan = result.plan
    _write_json_no_bom(args.out, plan)
    print(f"[OK] plano gravado: {args.out}")
    print(f"[OK] passos       : {len(plan['steps'])}")
    print(f"[OK] allowlist    : {', '.join(plan['required_allowlist'])}")

    if not plan["executable"]:
        print("[BLOQUEADO] plano NÃO executável. Lacunas de medição:")
        for gap in plan["measurement_gaps"]:
            print(f"  - {gap['kind']}: {gap['detail']}")
        print("O plano foi gravado assim mesmo: ele é a evidência do que falta")
        print("medir, e apagá-lo apagaria a explicação.")
        return EXIT_PLAN_NOT_EXECUTABLE

    print("[OK] executável   : sim")
    return EXIT_OK


if __name__ == "__main__":
    sys.exit(main())

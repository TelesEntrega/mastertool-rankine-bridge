# Contribuindo

## Princípios

1. Segurança antes de funcionalidade: nada que toque CLP, modo online ou projeto original.
2. Mudanças pequenas, testadas e documentadas.
3. APIs do MasterTool só entram no código após observadas no ambiente real e
   registradas em `docs/api/mastertool-api-observations.md`.

## Ambientes

| Local | Interpretador | Regras |
|-------|---------------|--------|
| `scripts/mastertool/` | IronPython 2.7 (dentro do MasterTool) | Sem f-strings, pathlib, type hints, dataclasses, pip |
| `src/`, `tests/`, `tools/` | Python 3.11+ | pytest obrigatório, cobertura ≥ 80% na camada crítica |

## Fluxo

1. Crie branch a partir de `main`.
2. Implemente + testes + docs no mesmo change.
3. `pytest` deve passar.
4. Commits pequenos e descritivos (imperativo, ≤ 72 chars no título).
5. Nunca versione projetos reais de clientes; use exemplos sintéticos em
   `tests/fixtures/` e `examples/`.

## Testes manuais (scripts internos)

Scripts que dependem do MasterTool têm roteiro manual em `docs/03-scripting-discovery.md`
e `docs/09-troubleshooting.md`: pré-condições, passos, resultado esperado, risco,
artefatos gerados e rollback quando aplicável.

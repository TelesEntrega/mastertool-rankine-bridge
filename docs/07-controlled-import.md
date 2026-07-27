# Importação controlada (Fase 4 — bloqueada)

## Estado

`09_import_selected_object.py`, `10_validate_import.py` e `11_rollback.py`
exibem apenas:

```text
Importação desabilitada. Conclua e aprove as fases de leitura, backup,
validação e compilação antes de habilitar esta funcionalidade.
```

`features.import: false` e `changes/approval.py`/`package_builder.py` levantam
`NotImplementedPhaseError`.

## Desenho previsto (para quando for liberada)

1. Change set validado (`mastertool-bridge validate-change-set`) — schema +
   política de segurança.
2. Backup da cópia de trabalho + verificação de `source_export_hash` (a
   alteração só se aplica sobre a exata versão de origem).
3. Importar SOMENTE objetos listados no change set, em cópia de trabalho.
4. Compilar; erro → abortar e restaurar backup.
5. Diff final gravado no pacote; aprovação humana registrada em `approval.md`.
6. Rollback disponível a qualquer momento a partir do backup.

## Portas de segurança (todas obrigatórias)

```text
cópia de trabalho → backup → diff textual → validação estrutural
→ compilação → aprovação humana
```

Risco crítico (saídas físicas, %Q, segurança de máquina, hardware, redes,
download) **nunca** é aplicado automaticamente — ver [08-safety.md](08-safety.md).

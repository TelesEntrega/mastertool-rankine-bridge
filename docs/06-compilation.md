# Compilação e coleta de mensagens (Fase 3 — não implementada)

## Estado

`06_compile_project.py` e `07_collect_messages.py` são estruturas informativas.
A compilação está **desabilitada** (`features.compile: false`) e só será
implementada quando:

1. as Fases 0 e 1 estiverem validadas no MasterTool 3.63;
2. a API real de compilação/mensagens estiver registrada em
   `docs/api/mastertool-api-observations.md` (saída dos scripts 01/02);
3. um humano habilitar `features.compile: true` conscientemente.

## Regras já definidas

- Compilar significa **verificar** a cópia de trabalho; nunca download, nunca online.
- Mensagens coletadas: erros, warnings, infos — com origem, objeto, localização,
  texto e timestamp — normalizadas para `compilation.json` (schema
  `compilation.schema.json`), mais `.md` e `.csv`.
- Qualquer erro de compilação **bloqueia** a continuidade do fluxo de alteração.

## Candidatos de API (a confirmar — NÃO usar antes da Fase 0)

O `01_discover_environment.py` testa a presença (sem invocar) de membros
plausíveis do ecossistema CODESYS, como `build`/`rebuild`/`clean` no projeto e
serviços de mensagens no objeto `system`. O resultado observado define a
implementação real.

# Arquitetura

## Dois ambientes Python, estritamente separados

### 1. Scripts internos (`scripts/mastertool/`)
- Executados DENTRO do MasterTool pelo menu de scripting.
- IronPython 2.7 (assumido; confirmar na Fase 0). Sem f-strings, pathlib,
  type hints, dataclasses ou pip.
- Só dependem do ScriptEngine e da stdlib; exportam dados em JSON/CSV/MD/ST.
- Não fazem análise complexa — apenas leitura e serialização.
- Módulos compartilhados em `scripts/mastertool/common/`:
  - `compatibility.py` — localização defensiva dos globais do ScriptEngine;
  - `project_access.py` — projeto primário, nomes, caminhos;
  - `tree_walker.py` — percurso da árvore com acesso guardado;
  - `object_reader.py` / `object_writer.py` (writer bloqueado nesta fase);
  - `file_io.py`, `checksums.py`, `logger.py`, `serialization.py`;
  - `safety.py` — bloqueios fail-closed espelhando `config/safety-policy.yaml`.

### 2. Aplicação externa (`src/mastertool_bridge/`)
- Python 3.11+, CLI `mastertool-bridge` (argparse).
- Nunca acessa o MasterTool/CLP: lê apenas os exports em `workspace/exports/`.
- Camadas:
  - `models/` — dataclasses (projeto, objeto, símbolo, referência, change set);
  - `schemas/` — JSON Schema dos artefatos;
  - `export/` — loader, validator (schemas+checksums), normalizer, indexer;
  - `analysis/` — parser ST tolerante, referências, grafo de chamadas,
    verificações de segurança (tudo heurístico);
  - `diff/` — diff textual objeto/projeto (semântico: fase 2);
  - `changes/` — modelo e validação de change sets (aplicação: fase 4);
  - `docs/` — geração de documentação Markdown/Mermaid.

## Fluxo de dados

```text
[MasterTool] --scripts 00-03--> workspace/exports/<ts>/           (imutável)
workspace/exports/<ts>/ --validate/index/analyze--> reports/      (CLI externa)
reports/ + índices --build-agent-context--> pacote p/ agentes IA
```

## Decisões de projeto

1. **Adaptadores, não suposições**: todo acesso à API do MasterTool passa por
   funções guardadas que retornam `None` + erro registrado quando o membro não
   existe. GUIDs/métodos observados vão para `docs/api/`.
2. **Exports imutáveis**: diretório com timestamp, nunca sobrescrito, com
   `checksums.sha256`.
3. **Fail closed**: sem política de segurança carregável → operação bloqueada.
4. **argparse em vez de Typer**: zero dependências extras para a CLI.
5. **Parser tolerante**: regex + registro de incertezas; não é um compilador
   IEC 61131-3 e não finge ser.

Diagramas: [diagrams/architecture.mmd](diagrams/architecture.mmd) e demais `.mmd`.

# Relatório — Primeira entrega (Fase 0, somente leitura)

Data: 2026-07-23 · Versão: 0.1.0 · Modo: read_only

## Arquivos criados (resumo por diretório)

| Diretório | Conteúdo |
|-----------|----------|
| raiz | README, AGENTS, CHANGELOG, CONTRIBUTING, LICENSE, .gitignore, .editorconfig, pyproject.toml, requirements-dev.txt |
| `config/` | default.yaml, safety-policy.yaml (normativo), logging.yaml, object-types.yaml, naming-rules.yaml |
| `docs/` | 00–10 (visão geral→roadmap), api/ (3 docs de observação de API), diagrams/ (4 Mermaid), INDEX.md |
| `scripts/mastertool/` | 00–03 implementados; 04–08 estruturas informativas; 09–11 importação desabilitada; `common/` com 12 módulos IronPython 2.7 |
| `scripts/windows/` | 5 .bat de orientação/atalho |
| `scripts/maintenance/` | clean-generated, validate-repository, generate-doc-index |
| `src/mastertool_bridge/` | CLI + models + schemas (5 JSON Schema) + export/ + analysis/ + diff/ + changes/ + docs/ + utils/ |
| `templates/` | 7 templates (AGENTS de projeto, relatórios, change request, risco, aprovação) |
| `tests/` | 26 unit + 14 integração/CLI (52 asserts de teste no total), fixtures sintéticas |
| `examples/` | sample-config.yaml, sample-change-set.json, READMEs |
| `workspace/` | estrutura com .gitkeep (conteúdo ignorado pelo Git) |
| `tools/` | 5 atalhos para a CLI |

## Funcionalidades

### Verificadas automaticamente (pytest: **52 passed**)
- Validação de export: manifesto, schemas JSON, checksums SHA-256, detecção de adulteração;
- Parser tolerante de declarações ST: cabeçalhos POU, EXTENDS, blocos VAR* (incl.
  RETAIN/PERSISTENT/CONSTANT), arrays, endereços `AT %QX`, valores iniciais, incertezas registradas;
- Busca heurística de referências: confirmed/probable read/write, unknown em chamadas;
- Verificações de segurança (heurísticas): `%Q` direto, variável em saída física,
  RETAIN/PERSISTENT, FOR com limite calculado, índice computado, ponteiros,
  conversões de tipo, múltiplos escritores, escrita-sem-leitura/leitura-sem-escrita;
- Diff textual objeto/projeto (added/removed/modified, whitespace-insensitive);
- Change sets: schema + política (crítico bloqueado, aprovação humana obrigatória,
  hardware proibido, `applied` rejeitado nesta fase);
- CLI completa: validate-export, inspect, index, analyze, document, compare,
  find-symbol/-reads/-writes, build-agent-context, validate-change-set;
- Scripts IronPython: sintaxe verificada (proxy CPython) e degradação graciosa
  comprovada fora do MasterTool (sem exceção, log gerado).

### Prontas para teste no MasterTool (não verificáveis aqui)
- `00_smoke_test.py`, `01_discover_environment.py`, `02_dump_api_surface.py`,
  `03_list_project_tree.py` — dependem do ScriptEngine real do MasterTool 3.63.

### Ainda não implementadas (propositalmente)
- `04/05` export completo (segunda entrega, após Fase 0 validada);
- `06/07` compilação/mensagens e `08` cópia de trabalho (terceira entrega);
- `09/10/11` importação/rollback (Fase 4 — bloqueada por política);
- diff semântico, máquinas de estado, duplicatas, complexidade (fase 2).

## Como executar

```bash
cd mastertool-rankine-bridge
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements-dev.txt
pip install -e .
pytest                      # esperado: 52 passed
mastertool-bridge --help
mastertool-bridge validate-export tests/fixtures/sample_project
```

No MasterTool 3.63 (menu de scripting, com projeto de teste aberto), executar em ordem:
`scripts/mastertool/00_smoke_test.py` → `01_discover_environment.py` →
`02_dump_api_surface.py` → `03_list_project_tree.py`.
Instruções detalhadas e resultados esperados: `docs/02-mastertool-setup.md` e
`docs/03-scripting-discovery.md`.

## Riscos e limitações

- **Nenhuma API do MasterTool foi confirmada**: `projects.primary`, `get_children`,
  `textual_declaration.text` etc. são convenções CODESYS acessadas defensivamente
  (hasattr + try/except); ausências são relatadas, nunca mascaradas.
- **IronPython 2.7 assumido** — a versão real será impressa pelo smoke test.
- Análises são **heurísticas** (parser regex, sem resolução de tipos): chamadas
  `var(...)` ficam como `unknown_usage`; membros `inst.var` não contam como
  referência à variável `var`; máquinas de estado ainda não são analisadas.
- Operações propositalmente desabilitadas: compilação (`features.compile: false`),
  importação (scripts 09–11 e `changes/approval|package_builder`), qualquer
  operação online/download (proibições permanentes em `config/safety-policy.yaml`).
- Repositório Git inicializado, **nenhum commit executado** (aguardando solicitação).

## Próximo passo recomendado

1. Executar **`scripts/mastertool/00_smoke_test.py`** dentro do MasterTool 3.63.
2. Se OK, executar `01`, `02` e `03` na sequência.
3. Devolver para análise:
   - `workspace/logs/*_00_smoke_test.log`
   - `workspace/exports/<ts>_discovery/environment.json`
   - `workspace/exports/<ts>_api-surface/api-surface.json`
   - `workspace/exports/<ts>_*_tree/project-tree.json`

Com esses arquivos, as APIs reais serão registradas em
`docs/api/mastertool-api-observations.md` e o exportador completo
(`04_export_project.py`) será implementado sobre fatos, não suposições.

# Relatório — Validação operacional ponta a ponta (MasterTool real → MCP)

Data: 2026-07-24 · Baseline comparada: `v0.1.0` (commit `8eddcb7`) · Modo: read_only
Executor: usuário, dentro do MasterTool IEC XE 3.63 real, projeto
`ExemploPlanta V1.0.project` — nova sessão, independente da captura de
2026-07-23 usada para construir a baseline `v0.1.0`.

**Veredito: APROVADO. Zero divergências encontradas em toda a cadeia.**
A tag `v0.1.0` **não foi alterada**.

## Trilha executada

```text
MasterTool real
→ 00_smoke_test.py                                  [verificado]
→ probes/12_validate_recursive_scanner.py            [verificado]
→ probes/13_validate_text_exporter.py                [verificado]
→ StaticProjectIndexer (build_static_index)           [verificado]
→ 5 famílias de consulta (find symbol/reads/writes/   [verificado]
  calls/callers)
→ ask() / ProjectIndex                                [verificado]
→ cliente MCP real (protocolo, não chamada direta)     [verificado]
```

## 1. `00_smoke_test.py`

Relatório: `workspace/logs/2026-07-24_14-15-03_00_smoke_test/report.json`.

Comparado campo a campo contra o contrato já documentado em
`docs/api/mastertool-api-observations.md` ("Runtime confirmado —
2026-07-23"):

| Campo | Baseline (2026-07-23) | Nova execução (2026-07-24) | Resultado |
|-------|------------------------|------------------------------|-----------|
| `sys.platform` | `cli` | `cli` | idêntico |
| `version_banner` | `MT8500.exe MasterTool IEC XE, ScriptEngine.plugin 4.1.0.0` | idêntico | idêntico |
| `projects` | presente, `ScriptProjects` | presente, `ScriptProjects` | idêntico |
| `system` | presente, `SystemImpl` | presente, `SystemImpl` | idêntico |
| `projects.primary` | presente, `ExtendedObject[IScriptProject]` | idêntico | idêntico |
| `dir(project)` | vazio (`members: []`) | vazio | idêntico (comportamento já conhecido) |
| `safety_declaration` | tudo `false` | tudo `false` | idêntico |

**Achado novo, não regressivo**: `runtime_version_evidence: "sys.version_info"`
confirma `IronPython 2.7.12` — resolve a pendência que o próprio doc
registrava ("investigar `sys.version_info` numa próxima rodada").

## 2. `probes/12_validate_recursive_scanner.py`

Relatório: `workspace/logs/2026-07-24_14-30-32_12_validate_recursive_scanner/`.
Checksums: **7/7 OK**.

| Métrica | Baseline | Nova execução | Resultado |
|---------|----------|-----------------|-----------|
| `total_nodes` | 117 | 117 | idêntico |
| `complete_nodes` | 117 | 117 | idêntico |
| `failed_nodes` | 0 | 0 | idêntico |
| `collection_errors`/`field_errors`/`index_errors` | 0/0/0 | 0/0/0 | idêntico |
| `duplicate_object_guids` | 0 | 0 | idêntico |
| `scan_complete` | true | true | idêntico |
| `expected_root_count` (4) bate | sim | sim | idêntico |

**GUIDs comparados byte a byte** (identidade dos 4 nós de topo + navegação
até a Application) — todos idênticos entre as duas execuções:

| Nó | `object_guid` | `type_guid` |
|----|-----------------|--------------|
| Project Settings | `6470a90f-b7cb-43ac-9ae5-94b2338b4573` | `8753fe6f-4a22-4320-8103-e553c4fc8e04` |
| Device | `ec2ca054-836f-492f-a95f-f296c4785352` | `225bfe47-7336-4dbc-9419-4105a7c831fa` |
| Device → Plc Logic | `ab0a1c6e-c69e-41f6-bb2a-9601c4989dbb` | `40b404f9-e5dc-42c6-907f-c89f4a517386` |
| Device → Plc Logic → Application | `00000000-0000-0000-0000-000000000001` | `639b491f-5557-464c-af91-1471bac9f549` |
| Project Information | `11c0fc3a-9bcf-4dd8-ac38-efb93363e521` | `085afe48-c5d8-4ea5-ab0d-b35701fa6009` |
| `__VisualizationStyle` | `5cce1091-f902-4a48-9357-89653e070a0d` | `8e687a04-7ca7-42d3-be06-fcbda676c5ef` |

## 3. `probes/13_validate_text_exporter.py`

Export: `workspace/exports/2026-07-24_14-30-44_13_validate_text_exporter/`.
Checksums: **158/158 OK**. `aborted_due_to_identity_mismatch: false`
(identidade da Application confirmada antes de qualquer leitura de texto).

| Métrica | Baseline | Nova execução | Resultado |
|---------|----------|-----------------|-----------|
| `total_nodes` | 92 | 92 | idêntico |
| `complete_nodes` | 92 | 92 | idêntico |
| `text_object_count` | 68 | 68 | idêntico |
| `declarations_saved` | 68 | 68 | idêntico |
| `implementations_saved` | 14 | 14 | idêntico |
| `total_characters_saved` | 66.360 | 66.360 | idêntico |
| `scan_complete` | true | true | idêntico |

`safety_declaration`: `write_operations_requested`/`compilation`/
`online_access`/`download`/`force`/`project_write`/`project_save`/
`project_close`/`object_creation`/`object_modification`/
`device_repository_access`/`device_configuration_access` — **todos
`false`** em ambas as execuções. Nenhuma escrita, build, sessão online,
download ou force ocorreu.

## 4. `StaticProjectIndexer` sobre o export novo

`build_static_index()` rodado sobre
`workspace/exports/2026-07-24_14-30-44_13_validate_text_exporter/`,
saída em `workspace/analysis/2026-07-24_validation_index/`.

| Artefato/métrica | Baseline (`v0.1.0`) | Novo export | Resultado |
|-------------------|----------------------|--------------|-----------|
| `symbols.json` (símbolos) | 60 | 60 | idêntico |
| `type-index.json` (tipos) | 8 (7 struct + 1 unknown) | 8 (7 struct + 1 unknown) | idêntico |
| `resolved-references.json` | resolved=409, partially_resolved=64, unresolved=61 | idêntico | idêntico |
| `resolved-calls.json` | resolved=3, unresolved=9 (total 12) | idêntico | idêntico |
| `read-write-index.json` (total de entradas) | 522 | 522 | idêntico |
| `diagnostics.json` (erros) | 0 | 0 | idêntico |
| `resolution-diagnostics.json` (erros) | 0 | 0 | idêntico |

**Nenhuma divergência em nenhum artefato.**

## 5. Cinco famílias de consulta, `ask`, `ProjectIndex`

Todas rodadas via `mastertool_bridge.ProjectIndex` contra o índice novo:

| Consulta | Resultado | Igual à baseline? |
|----------|-----------|---------------------|
| `find_symbol("TripTip")` | `ambiguous`, 2 candidatos | sim |
| `find_writes("TripTip")` | `found`, 13 ocorrências | sim |
| `find_calls("MainPrg")` | `resolved`, 3 (`SpecialVariablesPrg`/`StartPrg`/`UserPrg`) | sim |
| `find_callers("SpecialVariablesPrg")` | `resolved`, 1 (`MainPrg`) | sim |
| `find_symbol("VarMotores.MT01.RetornoDisjuntor")` | `resolved` | sim |
| `ask("onde VarMotores.MT01.RetornoDisjuntor é escrito?")` | `answered`, `limitations=[]` | sim |
| `ProjectIndex.metadata` | 60 símbolos/8 tipos/534 referências/12 chamadas | sim |

## 6. Cliente MCP real, ponta a ponta

Servidor subido como subprocesso real (`python -m mastertool_bridge.mcp_server`),
cliente MCP real conectado via stdio (`mcp.ClientSession`), protocolo de
verdade (não chamada direta de função):

- `list_tools()` → 8 tools esperadas, todas presentes.
- `open_project_index` → metadata idêntica à tabela acima, via protocolo.
- `find_symbol("TripTip")` → `ambiguous`/2, via protocolo.
- `find_calls("MainPrg")` → `resolved`/3, via protocolo.
- `ask_project(...)` → `answered`/`limitations=[]`, via protocolo.

## 7. Divergências registradas

**Nenhuma.** Todos os artefatos, contagens, GUIDs, estados de resolução e
respostas de consulta bateram exatamente entre a execução usada para
construir a baseline `v0.1.0` (2026-07-23) e esta nova execução
independente (2026-07-24), incluindo através do protocolo MCP real.

## Conclusão

A cadeia completa **MasterTool real → export → índice → consulta
determinística → resposta fundamentada → API Python → cliente MCP real**
está confirmada operacional e reprodutível numa segunda execução real,
independente da primeira. A tag `v0.1.0` permanece válida como baseline —
nenhuma correção foi necessária.

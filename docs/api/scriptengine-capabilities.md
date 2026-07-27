# Capacidades do ScriptEngine — mapa de confirmação

Estado de cada capacidade necessária ao projeto. Valores possíveis:
`confirmada-runtime` (rodou de fato dentro do MasterTool),
`evidência-estática` (reflection/strings sobre os binários instalados, sem
executar — ver `mastertool-api-observations.md`), `ausente`, `pendente`.

| Capacidade | Necessária para | Estado | Evidência |
|------------|-----------------|--------|-----------|
| Executar script Python pelo menu | tudo | **confirmada-runtime** | `00_smoke_test.py` rodou via menu Ferramentas em 2026-07-23 contra ExemploPlanta V1.0.project |
| Globais `projects`/`system` | acesso ao projeto | **confirmada-runtime** | presentes, tipos reais `ScriptProjects`/`SystemImpl` (ver `mastertool-api-observations.md`) |
| `projects.primary` | localizar projeto aberto | **confirmada-runtime** | presente e truthy, tipo `ExtendedObject[IScriptProject]`, `.path` legível |
| `dir()` sobre `ExtendedObject[T]` | 02_dump_api_surface / tree_walker | **confirmada-runtime — problemática** | retornou lista VAZIA sobre `projects.primary`, apesar de `.path` responder — ver "Achado importante" em mastertool-api-observations.md |
| Nome "curto" do projeto (distinto do path) | inventário/relatórios | **confirmada-runtime — ausente** | `get_object_name()` caiu no fallback `path`; `get_name()`/`.name` não encontrados neste objeto |
| `sys.version` como versão do Python | descoberta | **confirmada-runtime — não serve** | host sobrescreve com string do produto ("MT8500.exe ... ScriptEngine.plugin 4.1.0.0"), não é um número de versão de Python |
| `IScriptTreeObject.is_root` | posição na árvore | **confirmada-runtime** | `projects.primary.is_root == True` (2026-07-23, `probes/03_project_navigation.py`) — confirma que o wrapper dinâmico encaminha propriedades HERDADAS (não só as declaradas diretamente em `IScriptProject`) |
| `IScriptTreeObject.handle` | identificação interna | **confirmada-runtime — não usar como ID persistente** | `projects.primary.handle == 0` (2026-07-23); estabilidade entre execuções NÃO comprovada (uma única rodada) |
| `IScriptObject`/`IScriptProject.type`,`.guid` | identidade do objeto | **confirmada-runtime — AUSENTE em IScriptProject** | testado em 2026-07-23 (`probes/04_project_identity.py`): ambos `unsupported` (AttributeError) sobre `projects.primary` — confirma que nem a interface `IScriptProject` nem a classe concreta implementam `IScriptObject` |
| `IScriptProject.active_application` | acesso à Application | **confirmada-runtime** | `projects.primary.active_application` confirmado (2026-07-23); retorna objeto tipo `_3S.CoDeSys.ScriptDriverProjects.ScriptObject` (classe concreta), `Name=Application`, `guid` bate com arquivo `.compileinfo` observado independentemente. Promovido a `CAPABILITY_PROBES["project"]` |
| Percorrer árvore (get_children) | 03/04 | **confirmada-runtime** | `project.get_children(False)` confirmado (2026-07-23, `probes/05_children_collection.py`) — retorna `System.Collections.Generic.List<IExtendedObject<IScriptObject>>` real, `Count=4` (confirmado). `children[0..3]` (indexador nativo, todos os 4 índices) confirmados (`probes/06_first_child_identity.py` + `probes/07_remaining_top_level_children.py`); 5 de 5 critérios de reativação atendidos, mas `tree_walker.py` genérico segue suspenso até aprovação explícita de um `ProjectTreeAdapter` limitado — ver mastertool-api-observations.md |
| `children.Count` | tamanho da árvore | **confirmada-runtime** | `Count == 4` sobre `ExemploPlanta V1.0.project`, via `GetType().GetInterfaces()` confirmando `ICollection`/`IList` antes da leitura (sem `len()`) |
| `IScriptObject.is_folder`/`.type`/`.guid`/`.get_name(bool)` | identidade de nó da árvore | **confirmada-runtime** | testado em 2026-07-23 sobre `children[0]` (`probes/06_first_child_identity.py`): todos `confirmed`. `is_folder=False`, `type`/`guid` são GUIDs distintos (ambos confirmados `System.Guid`), `get_name(False)="Project Settings"`. Tipo concreto do nó: `_3S.CoDeSys.ScriptDriverProjects.ScriptObject` (mesmo de `active_application`) |
| `find` (busca por nome) | navegação | **evidência-estática forte (não-runtime)** | `IScriptTreeObject.find(names[])` / `find(name, recursive)` — mesma interface de `get_children`, ainda não testado |
| Ler declaração/implementação textual | export ST | **confirmada-runtime** | `IScriptObjectWithTextualDeclaration.textual_declaration` / `IScriptObjectWithTextualImplementation.textual_implementation` (retornam `IScriptTextDocument`, com `.text`) confirmados em `ScriptEngine3`. `common/read_only_text_exporter.py: ReadOnlyTextExporter` (2026-07-23) usa esses membros com `has_textual_declaration`/`has_textual_implementation` como portões booleanos obrigatórios; validado em runtime real contra `ExemploPlanta V1.0.project` (92 nós, 68 objetos com texto, 0 erros, checksums 158/158 OK) e 38 testes unitários (suíte completa: 225 passed, 1 skipped — ver `docs/12-read-only-text-export.md`) |
| `dir()` não enumera `ExtendedObject<T>` — CAUSA RAIZ | 02_dump_api_surface / tree_walker | **evidência-estática CONFIRMA a hipótese runtime** | `ExtendedObject<T>` implementa `System.Dynamic.IDynamicMetaObjectProvider` (protocolo dinâmico do DLR); membro real fica em campo privado `BASE_OBJECT`, encaminhado via `GetMetaObject()` — por isso `.path` funciona e `dir()` fica vazio |
| Export PLCopen XML | objetos gráficos | pendente | |
| Export nativo | raw/ | pendente | |
| API de compilação (build/check) | Fase 3 | evidência-estática | tipo `ScriptApplication` com `build()/rebuild()/clean()/generate_code()` confirmado no plugin ScriptDriverProjects |
| Leitura de mensagens de compilação | Fase 3 | evidência-estática | tipo `ScriptMessage` (project/object/position/text/severity) no plugin ScriptDriverSystem |
| Salvar projeto como (cópia) | Fase 3 (08) | pendente | |
| Import de objetos | Fase 4 | pendente | |
| Gerenciador de bibliotecas | inventário | pendente | string literal "library" encontrada, tipo não identificado ainda |
| Árvore de dispositivos | devices.json | evidência-estática | plugin ScriptDriverDeviceObject com `ScriptDeviceInstance`/`ScriptDeviceParameter` |
| Comparação nativa entre projetos | diff/project_diff (futuro) | evidência-estática | tipo `ScriptComparisonResult` (left_project/right_project/get_diff_state) |
| Dump oficial da API de scripting (`DumpScriptingApi`) | **OPCIONAL, não-bloqueante** (`status: unavailable_from_confirmed_script_scope`) | evidência-estática (assinatura COMPLETA) — **runtime: global ausente, 0 risco** | assinatura confirmada estaticamente (assembly/tipo/namespace/instancia/publico/virtual/7 parametros/retorno void). 1a execução controlada (2026-07-23): 0 chamadas realizadas. Script preservado, desabilitado (`features.official_api_dump: false`, padrão permanente). Não perseguir mais por hipótese |
| Global `scriptengine` (candidato a expor `DumpScriptingApi`) | idem | **confirmada-runtime — AUSENTE, sem nova tentativa autorizada** | testado em 2026-07-23 contra `ExemploPlanta V1.0.project`: não encontrado nem via escopo do script nem via `import scriptengine`/builtins. Decisão: parar de perseguir por hipótese (`system.<algo>`, outros nomes, service locators, varredura dinâmica) até nova evidência estática concreta |
| Operação online (NUNCA USAR) | proibido | evidência-estática | plugin ScriptDriverOnline confirmado presente — reforça necessidade da proibição; **não tocado** por `00_smoke_test.py` nem por `02_dump_api_surface.py` (whitelist estrita) |

## Modelo de introspecção (2026-07-23)

`dir()` deixou de ser fonte de verdade em qualquer script deste projeto — ver
"Modelo de introspecção — três estados" em `mastertool-api-observations.md`.
Toda descoberta nova passa por: evidência confiável → whitelist
(`common/capabilities.py: CAPABILITY_PROBES`) → acesso explícito por nome,
com `dir()` registrado apenas como diagnóstico não autoritativo.

## Catálogo estático de navegação (2026-07-23)

Pivô de arquitetura: em vez de perseguir `DumpScriptingApi` em runtime,
reflection estática direta sobre `ScriptEngine3.dll` mapeou a cadeia real:

```text
reflection estática completa → whitelist baseada em evidência
→ probes mínimos em runtime → adaptadores confirmados
```

Artefatos em `workspace/analysis/static-api/` (gitignored, regenerável via
`tools/static-api-catalog.ps1` + `tools/build-static-api-catalog.py`).

**Probe 1 executado em 2026-07-23** (`probes/03_project_navigation.py`):
`is_root` e `handle` **confirmados** em runtime. Confirma que o wrapper
`ExtendedObject<T>` encaminha propriedades herdadas de `IScriptTreeObject`,
não só as declaradas diretamente em `IScriptProject`.

**Probe 2 executado em 2026-07-23** (`probes/04_project_identity.py`):
`type`/`guid` **unsupported** (IScriptProject não implementa IScriptObject);
`active_application` **confirmed**. Todos os confirmados promovidos a
`common/capabilities.py: CAPABILITY_PROBES["project"]` (agora `["path",
"is_root", "handle", "active_application"]`).

**Correção de política aplicada**: serialização de objetos retornados nunca
mais usa `repr()`/`str()`/`.ToString()` em tipos `.NET` desconhecidos (só em
tipos primitivos/confirmados seguros) — centralizada em
`common/capabilities.py: build_representation()`. Ver "Correção de política"
em `mastertool-api-observations.md`.

**Probe 3 executado em 2026-07-23** (`probes/05_children_collection.py`):
`get_children(False)` **confirmed** — primeira chamada de método de
navegação da árvore. Retorna `List<IExtendedObject<IScriptObject>>` real,
`Count=4` confirmado. Marco: a cadeia mínima `projects → primary → path/
is_root/handle/active_application → get_children` está confirmada de ponta
a ponta.

**Probe 4 executado em 2026-07-23** (`probes/06_first_child_identity.py`):
`children[0]` (indexador nativo, único índice acessado) **confirmed**.
`is_folder`/`type`/`guid`/`get_name(False)` todos **confirmed**: primeiro
objeto de topo do projeto é **"Project Settings"** (`is_folder=False`,
`type`/`guid` GUIDs distintos, tipo concreto `_3S.CoDeSys.ScriptDriverProjects.ScriptObject`
— mesma classe de `active_application`). `tree_walker.py` segue suspenso.

**Probe 5 executado em 2026-07-23** (`probes/07_remaining_top_level_children.py`,
contra `ExemploPlanta V1.0.project` real, checksums verificados): lê
`children[1]`, `children[2]`, `children[3]` via tupla Python fixa (não itera
a coleção), com gate de `Count == 4` confirmado antes de qualquer acesso.
Todos os 12 probes de identidade (4 por índice) **confirmed**, 0 erros. Os
4 objetos de topo do projeto agora identificados: **"Project Settings"**
(índice 0), **"Device"** (índice 1), **"Project Information"** (índice 2),
**"__VisualizationStyle"** (índice 3) — nenhum é pasta (`is_folder=False`
em todos), todos com o mesmo tipo .NET concreto
(`_3S.CoDeSys.ScriptDriverProjects.ScriptObject`) mas `type` (GUID)
diferente entre si. Corrige de raiz o achado do probe 4 (campo `value` de
`get_name(False)` nulo por checagem redundante) usando o
`build_representation()` corrigido (reconhece `str`/`unicode` nativos sem
depender de `GetType()`) — confirmado em runtime: `value_available: true`
para os 3 nomes. **5 de 5 critérios de reativação do `tree_walker.py`
atendidos** (ver `mastertool-api-observations.md`); `tree_walker.py`
genérico segue suspenso até aprovação explícita de um `ProjectTreeAdapter`
limitado.

**Navegação recursiva generalizada e VALIDADA em runtime real (2026-07-23)**:
depois dos probes 05-10 confirmarem a mesma cadeia (`get_children(False)`
→ `Count` → indexador → identidade) em múltiplos níveis e índices, ela
foi generalizada em `common/read_only_project_scanner.py:
ReadOnlyProjectScanner` — scanner recursivo com limites obrigatórios,
isolamento de falhas por ramo e detecção conservadora de ciclos.
`tree_walker.py` **não** foi reativado (módulo novo e independente).
Execução real contra `ExemploPlanta V1.0.project` (checksums 8/8 OK): **117
nós, 100% completos, 0 erros, `scan_complete=true`** — árvore inteira do
projeto mapeada, incluindo confirmação cruzada de que
`Device → Plc Logic → Application` é o MESMO objeto que
`active_application` (mesmo `object_guid`). Único limite atingido:
profundidade máxima (4 nós de parâmetros de inversor em profundidade 7,
presentes mas não expandidos). **Fase de descoberta estrutural
considerada encerrada.** Ver `docs/11-read-only-project-scanner.md` e
`docs/api/mastertool-api-observations.md`.

Atualize esta tabela a cada rodada de descoberta, citando o export de origem
(runtime) ou o plugin analisado (estática). Evidência estática nunca deve ser
tratada como confirmação suficiente para destravar uma fase — apenas runtime
confirma.

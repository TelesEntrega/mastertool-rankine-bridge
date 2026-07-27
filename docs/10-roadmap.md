# Roadmap

## Entrega 1 — Fase 0 (esta entrega)
- [x] Estrutura do repositório, documentação, configs, política de segurança
- [x] Scripts 00-03 (smoke test, discovery, API surface, árvore)
- [x] Módulos comuns IronPython com acesso defensivo
- [x] CLI externa: validate-export, inspect, index, find-*, analyze, document,
      compare, build-agent-context, validate-change-set
- [x] Schemas JSON + testes unitários da camada externa
- [x] `00_smoke_test.py` executado com sucesso no MasterTool 3.63 real (2026-07-23,
      `ExemploPlanta V1.0.project`) — `projects`/`system`/`projects.primary` confirmados
- [x] Modelo de introspecção de 3 estados (`common/capabilities.py`) — `dir()`
      deixou de ser fonte de verdade após achado do proxy dinâmico
- [x] `02_dump_api_surface.py` reformulado: verificador de superfície conhecida
      (whitelist), não mais descobridor irrestrito
- [x] `common/tree_walker.py` suspenso (nomes de navegação nunca confirmados)
- [x] Assinatura completa de `ScriptEngine.DumpScriptingApi` extraída por
      reflection estática; script dedicado `probes/02_dump_official_scripting_api.py`
      criado e **desabilitado** (`features.official_api_dump: false`)
- [x] **Primeira execução controlada do dumper oficial** (2026-07-23,
      `ExemploPlanta V1.0.project`, cópia, sem online) — **resultado negativo,
      sem risco**: global `scriptengine` não encontrado, 0 chamadas
      realizadas, flag revertido para `false` (padrão permanente confirmado
      por diff). Ver "Runtime — primeira execução controlada" em
      mastertool-api-observations.md
- [x] **Decisão de arquitetura**: `DumpScriptingApi` marcado
      `status: unavailable_from_confirmed_script_scope`, `required: false`,
      `blocking: false`. Não perseguir mais por hipótese (sem tentar
      `system.<algo>`, outros nomes de global, service locators ou varredura
      dinâmica). Script preservado, desabilitado, não removido.
- [x] **Pivô**: reflection estática direta sobre `ScriptEngine3.dll`
      (assembly-núcleo compartilhado) mapeou a cadeia real de navegação —
      `IScriptTreeObject.get_children(bool)`/`.find(...)`,
      `IScriptObject.get_name(bool)`/`.type`/`.guid`, e confirmou
      `IScriptObjectWithTextualDeclaration`/`...Implementation` (bate com o
      design já implementado em `object_reader.py`). Ferramenta persistida:
      `tools/static-api-catalog.ps1` + `tools/build-static-api-catalog.py`.
      Artefatos em `workspace/analysis/static-api/` (7 arquivos, gitignored,
      regenerável). Ver "Catálogo estático de navegação" em
      mastertool-api-observations.md
- [x] Achado técnico confirmado: `ExtendedObject<T>` implementa
      `IDynamicMetaObjectProvider` — explica por que `dir()` fica vazio
      (protocolo dinâmico do DLR, não reflection tradicional)
- [x] **Probe de navegação executado** (2026-07-23, `ExemploPlanta V1.0.project`,
      `probes/03_project_navigation.py`): `is_root` (`True`) e `handle` (`0`)
      **confirmados em runtime**, isolados, sem parâmetros, sem escrita.
      Confirma que o wrapper `ExtendedObject<T>` encaminha propriedades
      HERDADAS de `IScriptTreeObject` (não só as declaradas diretamente em
      `IScriptProject`). Promovidos para `common/capabilities.py:
      CAPABILITY_PROBES["project"]` (agora `["path", "is_root", "handle"]`).
      `handle` NÃO deve ser usado como identificador persistente (estabilidade
      entre execuções não comprovada). Ver "Runtime confirmado — probe de
      navegação" em mastertool-api-observations.md
- [x] **Probe de identidade executado** (2026-07-23, `probes/04_project_identity.py`):
      `type`/`guid` **unsupported** (confirma que `IScriptProject` não
      implementa `IScriptObject`); `active_application` **confirmed**
      (retorna `_3S.CoDeSys.ScriptDriverProjects.ScriptObject`, `Name=Application`,
      `guid` bate com arquivo `.compileinfo` observado independentemente —
      `persistence_status: strongly_indicated`, não comprovado entre execuções).
      Promovido para `CAPABILITY_PROBES["project"]`
- [x] **Correção de política de serialização**: nunca mais `repr()`/`str()`/
      `.ToString()` em objetos `.NET` desconhecidos (uma execução real tinha
      usado `repr()`, que em IronPython invoca `ToString()` — chamada de
      método fora do escopo aprovado, sem efeito colateral observado, mas
      fora da letra da regra). Centralizado em `common/capabilities.py:
      build_representation()`. Testes: `tests/unit/test_strict_representation.py`
- [x] **Incidente registrado, artefatos reconstruídos e classificados**: um
      `rm -rf` com glob por sufixo apagou artefatos reais por engano;
      reconstruídos a partir de conteúdo já capturado na conversa e
      marcados explicitamente com `provenance: reconstructed_from_captured_output`/
      `original_runtime_artifact: false` (ver POLICY-DEVIATION-NOTE.md no
      diretório do run) — os checksums reconstruídos NÃO provam identidade
      com os arquivos apagados, só entre si
- [x] **Proteção permanente contra o incidente**: `scripts/maintenance/safe_clean_artifact.py`
      (lógica em `src/mastertool_bridge/utils/safe_cleanup.py`) — recusa
      glob, caminho vazio, caminho fora de `workspace/`, remoção de
      `workspace/logs` inteiro; exige arquivo sentinela `.mastertool-bridge-run`
      (gravado automaticamente por `common/file_io.new_export_dir`);
      dry-run é o padrão, remoção real exige `--confirm`. 15 testes em
      `tests/unit/test_safe_cleanup.py`
- [x] **Reorganização — numeração resolvida**: scripts exploratórios movidos
      para `scripts/mastertool/probes/` (`02_dump_official_scripting_api.py`,
      `03_project_navigation.py`, `04_project_identity.py`,
      `05_children_collection.py`), sem colidir mais com os scripts
      funcionais `04_export_project.py`/`05_export_selected_object.py` da
      Entrega 2. `00_smoke_test.py`/`01_discover_environment.py`/
      `02_dump_api_surface.py` permanecem na raiz (ferramentas permanentes)
- [x] **Probe de coleção de filhos executado** (2026-07-23,
      `probes/05_children_collection.py`): `get_children(False)`
      **confirmed** (1 chamada, 5ms) — retorna
      `System.Collections.Generic.List<IExtendedObject<IScriptObject>>`
      REAL (tipo concreto, não só a interface); `Count` **confirmed** = **4**
      (via `GetType().GetInterfaces()` confirmando `ICollection`/`IList`
      antes, sem `len()`). Sem iteração, sem stringificação. **Marco: cadeia
      mínima de navegação confirmada de ponta a ponta** (`projects` →
      `primary` → `path`/`is_root`/`handle`/`active_application` →
      `get_children`)
- [x] **Probe de identidade do primeiro filho executado** (2026-07-23,
      `probes/06_first_child_identity.py`): `children[0]` (indexador nativo)
      **confirmed**; `is_folder`/`type`/`guid`/`get_name(False)` todos
      **confirmed**. Primeiro objeto de topo do projeto = **"Project Settings"**
      (`is_folder=False`, tipo concreto `_3S.CoDeSys.ScriptDriverProjects.ScriptObject`
      — mesma classe de `active_application`). Adicionadas
      `capabilities.probe_method_call()`/`probe_indexer_access()`
      (mesma classificação tri-state, para chamadas com argumentos e acesso
      por índice). Achado colateral: campo de conveniência `value` do probe
      `get_name(False)` ficou `null` por checagem excessivamente
      conservadora (dado real está íntegro em `representation.value`) —
      registrado, não corrigido ainda
- [x] **Correção de política de serialização (2a rodada)**: `build_representation()`
      reconhecia `str` mas não `unicode` — em IronPython 2.7 isso fazia o
      campo de conveniência `value` de `get_name(False)` ficar `null` mesmo
      com o dado real íntegro em `representation.value` (achado registrado no
      probe 06). Corrigido via `_STRING_TYPES` (`basestring`/`str`, sem
      depender de `GetType()`); retorno de `build_representation()` ganhou
      `value_available`/`serialization_mode` (mantendo os campos originais).
      Testes ampliados em `tests/unit/test_strict_representation.py` (string
      nativa sem `dotnet_type` confirmado, `System.String` via fixture,
      objeto CLR desconhecido com `__repr__`/`__str__` que lançam exceção)
- [x] `01_discover_environment.py` segue com escopo NÃO ampliado
- [x] **Probe dos 3 elementos de topo restantes executado com sucesso**
      (2026-07-23, `probes/07_remaining_top_level_children.py`, contra
      `ExemploPlanta V1.0.project` real, checksums verificados 3/3 OK): gate de
      pré-condição `Count == 4` **confirmed**; `children[1]`, `children[2]`,
      `children[3]` via tupla Python fixa `AUTHORIZED_INDICES = (1, 2, 3)`
      (sem iteração da coleção); todos os 12 probes de identidade
      **confirmed**, 0 erros. Os 4 objetos de topo do projeto agora
      identificados: **Project Settings** (0), **Device** (1), **Project
      Information** (2), **__VisualizationStyle** (3) — nenhum é pasta,
      mesmo tipo .NET concreto mas `type` (GUID) distinto em cada um.
      Confirma em runtime a correção do campo `value` de `get_name(False)`
      (`value_available: true` para os 3 nomes)
- [x] **5 de 5 critérios de reativação do `tree_walker.py` atendidos** (ver
      tabela em mastertool-api-observations.md) — `tree_walker.py` genérico
      **segue suspenso**; reativação exige aprovação explícita separada
- [x] **Correção dos dados do índice 0** registrados no probe 06: `type`
      (`8753fe6f-4a22-4320-8103-e553c4fc8e04`) e `guid`
      (`00000000-0000-0000-0000-000000000144`) de "Project Settings" foram
      lidos com sucesso naquela execução (checksums re-verificados) e
      estavam registrados como "não lidos" por engano na documentação;
      corrigido — os 4 nós de topo estão integralmente identificados
- [x] **`ProjectTreeAdapter` implementado e aprovado** (2026-07-23,
      `common/project_tree_adapter.py`): snapshot limitado, profundidade
      fixa ≤ 1 (`MAX_SUPPORTED_DEPTH = 1`, sem parâmetro `recursive`),
      `Count` observado separado de `expected_count` opcional (mudança de
      objetivo adicionar um objeto legítimo ao projeto não é mais tratada
      como falha permanente da API), `max_children` como teto de segurança
      (`DEFAULT_MAX_CHILDREN = 64`). Regras impostas por construção:
      `get_children(False)`/`Count` uma única vez cada, acesso por índice
      via range Python local (nunca itera a coleção CLR), `get_name(False)`/
      `is_folder`/`type`/`guid` uma única vez por nó, sempre via
      `build_representation()`. Granularidade de falha: erro em
      `get_children`/`Count`/índice aborta o snapshot; erro isolado em um
      campo de identidade não aborta os demais. Retorno 100% serializável
      (nenhum proxy do ScriptEngine vaza). 21 testes com fakes em memória
      em `tests/unit/test_project_tree_adapter.py` (coleção vazia, 1/4
      elementos, `Count` negativo/excedente/divergente do esperado, falha
      isolada por campo, falha no indexador interrompe sem tentar índices
      seguintes, chamada única garantida por membro, coleção nunca
      iterada, nenhum proxy no resultado, objeto com `__repr__`/`__str__`
      explosivos tratado com segurança, recusa de profundidade > 1)
- [x] **`ProjectTreeAdapter` validado em runtime real** (2026-07-23,
      `probes/08_validate_root_adapter.py`, contra `ExemploPlanta V1.0.project`,
      checksums verificados 3/3 OK): `collection.state=confirmed`,
      `count=4`, `count_matches_expected=true`, `complete=true`, **0
      erros**. Os 4 nós retornados pelo adaptador (nome, `is_folder`,
      `type_guid`, `object_guid`) batem EXATAMENTE, GUID por GUID, com os
      já confirmados isoladamente nos probes 06/07 — confirma que o
      adaptador reproduz fielmente, de forma genérica e reutilizável, o
      mesmo dado antes obtido por scripts de probe individuais. `root.path`/
      `root.is_root` também confirmados. Primeiro consumidor real e
      auditado da cadeia de navegação
- [ ] `tree_walker.py` poderá, no futuro, passar a consumir o
      `ProjectTreeAdapter` em vez de acessar o ScriptEngine diretamente —
      não implementado ainda; segue suspenso
- [x] **Decisão**: o próximo nó a testar é **Device** (`root_children[1]`),
      não `active_application` — `Device` valida a navegação hierárquica
      GENÉRICA (mesmo caminho `get_children(False)` que qualquer outro nó
      usaria); `active_application` é um atalho direto do projeto, útil só
      como confirmação cruzada posterior
- [x] **`probes/09_device_children_collection.py` criado** (2026-07-23):
      primeiro teste de navegação em 2 níveis
      (`projects.primary → Device → get_children(False)`). Revalida, NESTA
      execução (sem reaproveitar dados de probes anteriores),
      `root_children.Count == 4` e a identidade de `root_children[1]`
      (nome="Device", `type`/`guid` batendo com os GUIDs já confirmados)
      ANTES de chamar `device.get_children(False)`; diverência em qualquer
      identidade registra `device_identity_mismatch` e aborta sem tocar
      `device.get_children`. No próprio Device, autoriza só
      `get_children(False)` + verificação de nulidade/tipo/interface
      `ICollection`/`IList` + leitura de `Count` (sem indexar/iterar/ler
      nomes dos filhos de Device). Validado externamente (fora do
      MasterTool) com harness de 7 cenários usando fakes em memória:
      sucesso total, `root_count_mismatch` (aborta sem acessar índice 1),
      `device_identity_mismatch` (aborta sem chamar `device.get_children`),
      `Count==0` (válido), `Count<0` (inválido), `Count>64` (inválido,
      limite de segurança), coleção sem interface `ICollection`/`IList`
      (Count nunca tentado) — todos os 7 se comportaram exatamente como
      especificado.
- [x] **Navegação em 2 níveis confirmada em runtime real** (2026-07-23,
      `probes/09_device_children_collection.py`, contra
      `ExemploPlanta V1.0.project`, checksums verificados 3/3 OK): identidade
      de `Device` revalidada nesta execução (`name="Device"`, `type`/`guid`
      batendo com os GUIDs já confirmados) → `device.get_children(False)`
      **confirmed** → tipo .NET concreto do retorno IDÊNTICO ao da coleção
      da raiz (`System.Collections.Generic.List<IExtendedObject<IScriptObject>>`)
      → confirma `ICollection`/`IList` (8 interfaces observadas, incluindo
      `IReadOnlyList`/`IReadOnlyCollection`) → `Count = 2`, válido. **0
      erros**. Marco: a MESMA cadeia de navegação (`get_children(False)` →
      `Count` → indexador) funciona identicamente em um nó filho, não só
      na raiz — primeira prova de que a descida pela árvore é genérica
- [x] **`common/device_first_child_probe.py` criado** (2026-07-23): função
      PURA (sem I/O), extraída para ser testável com fakes em memória —
      mesmo padrão de `common/project_tree_adapter.py`. Identifica SOMENTE
      `device_children[0]`, sem misturar com `active_application` (fica
      para outro probe, para não dificultar isolar a causa de uma
      eventual falha). Fluxo: revalida `root_children.Count == 4` →
      `root_children[1]` → revalida identidade de Device NESTA execução
      (nome/`type`/`guid`, sem reaproveitar dados de probes anteriores) →
      `device.get_children(False)` (só com identidade confirmada) →
      confirma coleção não nula + interface `ICollection`/`IList` +
      `Count == 2` → `device_children[0]` (indexador único, NUNCA índice
      1) → 4 probes isolados de identidade (`is_folder`/`type`/`guid`/
      `get_name(False)`). Para `type`/`guid` do PRIMEIRO FILHO, o valor só
      é serializado quando `GetType()` confirma exatamente `System.Guid`
      (restrição mais estrita que `build_representation()` isolado,
      pedida explicitamente pelo usuário). 16 testes PERMANENTES em
      `tests/unit/test_device_first_child_probe.py`: sucesso completo,
      raiz com `Count != 4`, identidade de Device divergente (nome e
      type/guid), `Count` de Device `!= 2`, coleção sem interface de
      contagem, falha no indexador 0, falha isolada em cada campo de
      identidade (nome/is_folder/type/guid ausente), valor só serializado
      quando confirmado `System.Guid`, garantia de que `device_children[1]`
      nunca é acessado, garantia de que `root_children` só acessa índice
      1, garantia de que o primeiro filho nunca recebe `get_children()`,
      mais falhas estruturais mais cedo na cadeia (get_children da raiz,
      coleção nula)
- [x] **`probes/10_device_first_child_identity.py` criado** (2026-07-23):
      wrapper fino sobre `common/device_first_child_probe.py` — resolve
      `projects.primary`, chama a função pura, grava relatório. Dry-run
      fora do MasterTool confirma degradação graciosa.
- [x] **Primeiro filho de Device identificado em runtime real** (2026-07-23,
      contra `ExemploPlanta V1.0.project`, checksums verificados 3/3 OK,
      **0 erros**): `root_children.Count=4` e identidade de `Device`
      revalidados; `device.get_children(False)` confirmado (mesmo tipo
      concreto/interfaces do probe 09), `Count=2` confirmado;
      `device_children[0]` confirmado. Resultado: **"Plc Logic"**
      (`is_folder=False`, `type=40b404f9-e5dc-42c6-907f-c89f4a517386`,
      `guid=00000000-0000-0000-0000-000000000177`) — **NÃO é a Application**
      (então, por decisão já registrada: o próximo probe deve acessar
      somente `device_children[1]`, não comparar com `active_application`
      ainda)
- [x] **Mudança de estratégia (2026-07-23)**: parar de criar um probe por
      índice/execução. `common/read_only_project_scanner.py:
      ReadOnlyProjectScanner` criado — scanner recursivo genérico, somente
      leitura, com limites obrigatórios (`max_depth`/`max_total_nodes`/
      `max_children_per_node`), isolamento de falhas por ramo, detecção
      conservadora de ciclos (por `object_guid` entre ancestrais, nunca por
      `handle`), e saída 100% serializável. Generaliza a MESMA cadeia já
      confirmada nos probes 05-10 (`get_children(False)` → `Count` →
      indexador → identidade) para qualquer profundidade. `tree_walker.py`
      **NÃO foi reativado** — módulo novo e independente. Ver
      `docs/11-read-only-project-scanner.md` para a especificação completa.
      31 testes PERMANENTES em `tests/unit/test_read_only_project_scanner.py`
      cobrindo estrutura (árvore vazia, múltiplos níveis, profundidade
      máxima, limites de filhos/nós excedidos), navegação (chamada única
      por nó, ordem preservada, caminho de índices correto), identidade
      (campos confirmados/ausentes/com exceção, objeto com `__repr__`/
      `__str__` explosivos), falhas (isoladas por ramo, nunca abortam o
      scan inteiro exceto o limite global de nós), segurança (nenhum proxy/
      coleção CLR no resultado) e ciclos/duplicidades (GUID duplicado entre
      ramos distintos vs. ciclo real por ancestralidade). `probes/12_validate_recursive_scanner.py`
      criado como wrapper fino (resolve `projects.primary`, roda uma
      varredura com limites conservadores para a primeira execução —
      `max_depth=6, max_total_nodes=2000, max_children_per_node=128,
      expected_root_count=4`, este último específico de
      `ExemploPlanta V1.0.project`). `config/scanner-defaults.yaml` criado com
      os limites genéricos padrão. Validado externamente: dry-run sem
      `projects` (degradação graciosa) e uma segunda execução com árvore
      sintética via fakes espelhando a estrutura real já confirmada
      (Project Settings/Device→Plc Logic+Bus/Project Information/
      __VisualizationStyle) — 8 artefatos gerados corretamente,
      estatísticas e índices corretos, 0 erros.
- [x] **`ReadOnlyProjectScanner` validado em runtime real com sucesso
      total** (2026-07-23, `probes/12_validate_recursive_scanner.py`,
      contra `ExemploPlanta V1.0.project`, checksums verificados 8/8 OK):
      **117 nós, 100% completos (0 parciais, 0 falhos), 0 erros de
      campo/coleção/índice, 0 GUIDs duplicados, `scan_complete=true`**.
      `root_count_matches_expected=true` (`Count==4` bateu). Único limite
      atingido: `max_depth_reached=true` (4 nós em `profundidade 7`,
      dentro do device de rede `EtherNet_IP_Scanner`, tiveram a busca de
      filhos interrompida — nós presentes na árvore, apenas não
      expandidos). Estrutura completa da árvore descoberta — ver detalhes
      em `docs/api/mastertool-api-observations.md`, incluindo a
      **confirmação cruzada Application ↔ active_application**: o nó
      `root/1/0/0` ("Application", achado pela navegação hierárquica via
      `Device → Plc Logic`) tem o MESMO `object_guid`
      (`00000000-0000-0000-0000-000000000001`) já registrado para
      `active_application` desde o probe 04 — confirma que o caminho
      hierárquico genérico chega ao MESMO objeto que o atalho direto.
      `tree_walker.py` permanece suspenso

## Entrega 2 — Fase 1/2 (após validar Fase 0)
- [x] `ReadOnlyProjectScanner` validado em runtime real contra
      `ExemploPlanta V1.0.project` (`probes/12_validate_recursive_scanner.py`)
- [x] **Leitura textual implementada** (2026-07-23): `common/read_only_text_exporter.py:
      ReadOnlyTextExporter` — exportador textual DFS iterativo, somente
      leitura, entrando pela Application (não pela raiz do projeto),
      testando `has_textual_declaration`/`textual_declaration.text`/
      `has_textual_implementation`/`textual_implementation.text` como
      portões booleanos obrigatórios (nunca acesso especulativo) em cada nó
      da subárvore. Reaproveita o mesmo vocabulário de estados de coleção
      do scanner já aprovado (cópia local, autocontida — sem import cruzado
      com `read_only_project_scanner.py`). Separação pura/impura:
      `export()` nunca toca disco (monta a árvore + texto em memória);
      `write_text_export_artifacts()` é uma camada fina separada que só
      serializa o que já foi decidido. Limites adicionais obrigatórios:
      `max_text_objects`, `max_document_characters`, `max_total_characters`.
      Preservação exata do texto lido (sem normalização/strip, SHA-256 por
      documento, `character_length` vs. `byte_length`).
      `probes/13_validate_text_exporter.py` criado como wrapper fino
      (sonda a identidade da Application e aborta ANTES de qualquer leitura
      textual se divergir dos `expected_*` de `ExemploPlanta V1.0.project`).
      `config/text-export-defaults.yaml` criado com os limites genéricos
      padrão. 37 testes permanentes em
      `tests/unit/test_read_only_text_exporter.py`. Validado **externamente**
      (fora do MasterTool): dry-run sem `projects` (degradação graciosa) e
      uma execução com árvore sintética via fakes (POU com
      declaração+implementação multiline com acentos/CRLF, GVL só com
      declaração, DUT só com declaração, pasta sem texto, texto vazio,
      erros simulados nos indicadores) — texto e SHA-256 conferidos
      byte-a-byte em memória e em disco, 4 diretórios `objects/` gravados
      corretamente. Ver `docs/12-read-only-text-export.md`.
- [x] **Exportação textual validada em runtime real com sucesso total**
      (2026-07-23, `probes/13_validate_text_exporter.py`, contra
      `ExemploPlanta V1.0.project`, checksums 158/158 OK): identidade da
      Application confirmada (`name="Application"`, GUIDs batendo com os
      `expected_*`); **92 nós, 100% completos, 0 parciais, 0 falhos, 0
      erros**; **68 objetos com texto** (68 declarações + 14
      implementações, todas as 14 com ambos), **66.360 caracteres**
      exportados, nenhum limite atingido. Nenhuma escrita/compilação/acesso
      online — confirmado pela `safety_declaration` e por `errors.json`
      vazio. Um FB real inspecionado (`FB_VALVULA_EXEMPLO`) confirma
      preservação exata (indentação com tabs/espaços mistos intacta).
      Revisão pós-execução encontrou 1 gap real no artefato gerado
      (`text-index.json` fora do schema pedido — corrigido via delta-fix,
      índice regenerado a partir da árvore já exportada, sem nova execução
      no MasterTool; números cruzados e batendo exatamente com as
      estatísticas do `report.json` original). `tree_walker.py` permanece
      suspenso. **Fase de exportação textual considerada validada.**
- [x] **Checkpoint Git criado** (2026-07-24, commit `14e4bbb`, primeiro
      commit do repositório): consolida toda a base validada até aqui —
      probes 03-13, `ProjectTreeAdapter`, `ReadOnlyProjectScanner`,
      `ReadOnlyTextExporter`, os 4 achados corrigidos na revisão pós-execução
      (`safety_declaration`, `metadata.json`, boundary de erros por nó,
      `text-index.json`), testes permanentes, configs, documentação. Exclui
      `workspace/` (gitignored), artefatos exportados, e qualquer arquivo
      `.project`/`.compileinfo` do MasterTool (nenhum existe dentro do
      repositório).
- [x] **`StaticProjectIndexer` implementado e validado end-to-end**
      (2026-07-24, 12 commits `36dda15`→`523f443`, cada um verificado
      independentemente antes de commitar): parser ST determinístico
      (tokenização → statements → declarações, nunca só regex),
      resolução de símbolos em 7 níveis de prioridade (nunca escolhe
      candidato por suposição em ambiguidade), classificação read/write
      por regra fixa de contexto+operador, 11 artefatos JSON estáveis
      (`symbols`/`references`/`calls`/`type-index`/`read-write-index`/...),
      DUT/STRUCT indexado (cadeias `GVL.Instancia.Membro` resolvem de
      verdade), 5 consultas determinísticas (`find symbol/reads/writes/
      calls/callers`), parser de intenção em PT/EN controlado (zero IA/
      fuzzy), respostas fundamentadas em evidências, API Python pública
      (`mastertool_bridge.ProjectIndex`), servidor MCP fino (8 tools).
      Ver `docs/13-static-project-indexer.md` e
      relatorios de validacao internos (nao publicados) para arquitetura e validação
      completas. `tree_walker.py` continua suspenso — scanner e
      exportador já cobrem sua finalidade original de forma validada e
      auditável.
- [ ] `04_export_project.py` (exportador principal) e `05_export_selected_object.py`
- [ ] Manifesto completo + checksums + inventário gerados no export real
      (`workspace/exports/<timestamp>/manifest.json` + `project-tree.json` +
      `objects/{programs,function-blocks,functions,methods,actions,gvls,duts}/`
      + `errors.json` + `checksums.sha256`)
- [ ] Diff semântico, máquinas de estado, duplicatas, complexidade
- [ ] Documentação automática sobre export real

## Entrega 3 — Fase 3
- [ ] `06_compile_project.py` (com `features.compile` explícito) e `07_collect_messages.py`
- [ ] Normalização de diagnósticos, comparação entre exports em CI
- [ ] Change sets completos (pacote físico, análise de risco, aprovação)
- [ ] `08_create_working_copy.py`

## Entrega 4 — Fase 4 (somente após 0-3 aprovadas)
- [ ] Importação controlada (09/10/11) com backup, hash de origem e rollback

## Futuro (fora de escopo atual)
- [x] Servidor MCP expondo as operações de leitura/análise para agentes —
      **entregue** (`src/mastertool_bridge/mcp_server.py`, commit `523f443`),
      cobrindo a camada de indexação/consulta já validada (descoberta→
      exportação→indexação→consulta ficaram confiáveis; compilação/
      alteração controlada continuam nas Entregas 3/4, ainda não
      iniciadas)
- [ ] Parse de ENUM/UNION/INTERFACE (DUT/STRUCT já cobre a maior parte dos
      casos reais observados — enum reconhecido como tipo existente, mas
      não indexado por membro; não é bloqueante para a integração
      operacional completa)
- [x] Retomar `00_smoke_test.py` no MasterTool real como nova trilha
      controlada — **concluído** (2026-07-24): validou a cadeia completa
      MasterTool → export → índice → consulta → MCP contra uma nova
      execução real, zero divergências vs. `v0.1.0`. Ver
      relatorios de validacao internos (nao publicados).

## Entrega 5 — Ladder, FBD/SFC, documentação automática e agentes (roadmap registrado 2026-07-24)

Ver `docs/14-ladder-roadmap.md` para a especificação completa (visão de
produto, arquitetura alvo, fases L0–L8, versionamento v0.2→v1.0, ordem de
execução recomendada, e o registro vivo de estado de execução).

- [ ] **L0 — Inventário e classificação**: em andamento. Reconhecimento
      offline (sem tocar o MasterTool) já encontrou 25 candidatos a
      implementação não-textual nos exports reais já capturados — falta a
      confirmação em runtime real (`probes/14_inventory_graphic_pous.py`,
      só o usuário pode executar dentro do MasterTool).
- [ ] L1–L8 (descoberta → aquisição → modelo canônico → parser →
      semântica → unificação com ST → validação real → FBD/SFC): não
      iniciadas, dependem do resultado de L0/L1 em runtime real —
      "implementar a semântica antes de conhecer o formato real criaria
      uma arquitetura baseada em suposições" (mesma regra já seguida em
      toda a trilha ST).

# Diário técnico — APIs observadas no MasterTool IEC XE 3.63

> Registre aqui o que foi observado, seja em **runtime** (saídas dos scripts
> 00-03 rodando de fato dentro do MasterTool) ou por **evidência estática**
> (análise read-only dos binários instalados, sem executar nada). Cada seção
> indica a fonte. Nada de suposições sem marcar a origem.

## Nota metodológica — evidência estática (2026-07-23)

MasterTool IEC XE 3.63 está instalado nesta máquina em
`C:\Program Files (x86)\Altus\MT8500 3.63\MT8500\`. Antes de qualquer execução
real, foi feita uma análise **puramente estática** dos assemblies .NET dos
plugins de scripting, usando `Assembly.ReflectionOnlyLoadFrom` (PowerShell) —
isso **carrega apenas metadados, não executa nenhum código** — mais extração
de strings literais dos binários (procura de identificadores como `"projects"`,
`"system"`, `"primary"` no heap de strings do assembly). Nenhum projeto foi
aberto, nenhum processo do MasterTool foi iniciado.

Plugins relevantes encontrados em `MT8500\PlugIns\<guid>\4.x.0.0\`:

| Plugin | Namespace .NET | Papel provável |
|--------|-----------------|-----------------|
| `ScriptDriverProjects.plugin.dll` | `_3S.CoDeSys.ScriptDriverProjects` | registra o global `projects` |
| `ScriptDriverSystem.plugin.dll` | `_3S.CoDeSys.ScriptDriverSystem` | registra o global `system` |
| `ScriptEngine.plugin.dll` | `_3S.CoDeSys.ScriptEngine` | motor de scripting em si |
| `ScriptDriverOnline.plugin.dll` | `_3S.CoDeSys.ScriptDriverOnline` | operações online — **NUNCA USAR** |
| `ScriptDriverDeviceObject.plugin.dll` | `_3S.CoDeSys.ScriptDriverDeviceObject` | árvore de dispositivos |

As classes `ScriptDriverProjects`/`ScriptDriverSystem`/`ScriptDriverDeviceObject`
em si são **drivers/fábricas** (método `OnDriverLoad(IScriptExecutor executor)`)
que registram os globais em tempo de execução — a IL desse método não foi
decompilada, então o nome exato do global só é 100% confirmado rodando
`01_discover_environment.py` de verdade. A extração de strings, porém, achou
os literais `"projects"`, `"primary"`, `"project"`, `"application"`,
`"library"` dentro de `ScriptDriverProjects.plugin.dll` e o literal `"system"`
dentro de `ScriptDriverSystem.plugin.dll` — evidência forte (não prova
definitiva) de que os nomes assumidos em `common/compatibility.py`
(`CANDIDATE_GLOBALS`) e `common/project_access.py` (`projects.primary`) estão
corretos.

**Achado mais importante:** `_3S.CoDeSys.ScriptEngine.ScriptEngine` expõe um
método público de dump oficial da API de scripting (namespace `DocuDumper`
inteiro dedicado a isso: `Root`, `EntryPointImpl`, `TypeInfoImpl`,
`MemberInfoImpl`, `AssemblyInfoImpl` etc.).

### Assinatura completa de `DumpScriptingApi` (reflection estática detalhada, 2026-07-23)

Extraída via `Assembly.ReflectionOnlyLoadFrom` sobre
`ScriptEngine.plugin.dll` v4.1.0.0 (metadados apenas — nenhum código
executado):

| Campo | Valor |
|-------|-------|
| Assembly | `ScriptEngine.plugin, Version=4.1.0.0, Culture=neutral, PublicKeyToken=null` |
| Tipo declarante | `_3S.CoDeSys.ScriptEngine.ScriptEngine` (classe pública) |
| Namespace | `_3S.CoDeSys.ScriptEngine` |
| Método | `DumpScriptingApi` |
| Estático? | **Não** — método de instância (`IsStatic: False`) |
| Visibilidade | Público, virtual, não abstrato |
| Retorno | `System.Void` |
| Overloads | 1 (sem sobrecarga) |

Parâmetros (**somente o `[0]` é obrigatório; `[1]` a `[6]` são `OPTIONAL`,
default `null`** — confirmado via `ParameterInfo.IsOptional`/`DefaultValue`):

```text
[0] System.IO.TextWriter                                          outputWriter        (obrigatório)
[1] _3S.CoDeSys.ScriptEngine.LogCallback                           logCallback         (opcional, default null)
[2] _3S.CoDeSys.ScriptEngine.DriverFilter                          allowedDrivers      (opcional, default null)
[3] System.Predicate<System.Object>                                allowedObjects      (opcional, default null)
[4] IEnumerable<KeyValuePair<System.String,System.Object>>         additionalEntryPoints (opcional, default null)
[5] IEnumerable<System.Reflection.Assembly>                        additionalAssemblies  (opcional, default null)
[6] _3S.CoDeSys.ScriptEngine.IScriptExecutor4                      speciallyPreparedExecutor (opcional, default null)
```

Implicações:
- Em IronPython, `engine.DumpScriptingApi(writer)` (só o obrigatório) ou
  `engine.DumpScriptingApi(writer, None, None, None, None, None, None)`
  (explícito) devem ambos ser sintaticamente válidos — parâmetros opcionais
  do CLR são respeitados pelo binder do IronPython.
- `outputWriter` exige um `System.IO.TextWriter` .NET real — em IronPython,
  `System.IO.StringWriter()` (não o `StringIO` do Python) é o candidato
  correto para capturar a saída em memória.
- Os tipos `LogCallback`/`DriverFilter` (delegates) **não foram localizados**
  em `ScriptEngine.plugin.dll` — provavelmente definidos em outro
  assembly-núcleo ainda não pesquisado. Não bloqueia a chamada, já que são
  opcionais.

Script dedicado (permanece **desabilitado** por `features.official_api_dump:
false`, o padrão permanente do repositório): `scripts/mastertool/probes/02_dump_official_scripting_api.py`.
A assinatura acima está espelhada em `EXPECTED_SIGNATURE` nesse arquivo,
registrada no relatório **antes** de qualquer tentativa de chamada.

### Runtime — primeira execução controlada (2026-07-23) — RESULTADO NEGATIVO, SEM RISCO

`features.official_api_dump` foi habilitado localmente por uma única
execução (`ExemploPlanta V1.0.project`, cópia, sem conexão online) e revertido
para `false` imediatamente depois. Resultado:

- **Global `scriptengine` NÃO encontrado** — nem diretamente no escopo do
  script (`globals()`), nem via `compatibility.get_scriptengine_global`
  (fallback `import scriptengine` / builtins).
- `scriptengine_object.found = false`, `resolution_method = null`,
  `has_dump_method = null`.
- **Zero chamadas realizadas** (`invocation.call_count = 0`,
  `attempted = false`) — nenhuma exceção, nenhum risco incorrido.
- Relatório completo: `workspace/logs/2026-07-23_10-54-06_02_dump_official_scripting_api/`
  (`report.json`, `report.md`, `checksums.sha256` — checksums verificados,
  íntegros).

**Conclusão:** o nome `scriptengine` (usado em `common/compatibility.py` como
candidato desde a Fase 0) **não é o nome do global real**, ou o objeto que
expõe `ScriptEngine`/`DumpScriptingApi` não é exposto diretamente a scripts
do jeito que presumimos — apenas aos dois nomes já confirmados (`projects`,
`system`). Isso NÃO invalida a assinatura estática de `DumpScriptingApi` (ela
continua correta como propriedade do tipo .NET); só significa que ainda não
sabemos **como alcançar uma instância desse tipo a partir de um script**.

Hipóteses a considerar (não testadas ainda, aguardando decisão antes de
qualquer nova tentativa — não presumir nenhuma delas):
1. O objeto `system` (já confirmado, tipo `SystemImpl`) pode expor o motor
   de scripting por algum outro caminho (ex.: `system.<algo>.DumpScriptingApi`) —
   precisaria de sondagem explícita e autorizada de um novo candidato via
   `capabilities.CAPABILITY_PROBES["system"]`, não de enumeração livre.
2. O global pode ter outro nome não cogitado ainda (`scripting`, `engine`,
   `script_engine`, etc.) — qualquer novo candidato exigiria justificar
   evidência antes de adicionar à whitelist, conforme o modelo de três
   estados.
3. `DumpScriptingApi` pode não ser exposto a scripts IronPython de forma
   alguma (pode ser uma API interna usada só por outras partes do produto).

Nenhuma dessas hipóteses foi testada nesta execução.

### Decisão de arquitetura (2026-07-23): `DumpScriptingApi` vira opcional

A ausência do global `scriptengine` **não prova que o método é inexistente
ou impossível de acessar** — prova só que a instância de
`_3S.CoDeSys.ScriptEngine.ScriptEngine` não está exposta ao escopo do script
pelo nome testado. Decisão: parar de perseguir `DumpScriptingApi` em runtime
por hipótese (não tentar `system.<algo>`, outros nomes de global, imports
adicionais, service locators ou varredura dinâmica). Ele passa a ser:

```text
status:   unavailable_from_confirmed_script_scope
required: false
blocking: false
```

`features.official_api_dump` permanece `false` (padrão permanente).
`scripts/mastertool/probes/02_dump_official_scripting_api.py` é preservado como
recurso experimental desabilitado — **não removido**. Nova tentativa de
runtime só é autorizada se a reflection estática identificar uma das
evidências abaixo (nenhuma encontrada até agora):
- uma propriedade em um objeto já confirmado (`projects`, `system`, ou algo
  alcançável a partir deles) que retorne um `ScriptEngine`;
- um singleton público de `ScriptEngine`;
- um serviço publicamente acessível que o exponha;
- ou um global registrado com nome literal comprovado (string encontrada nos
  metadados, como fizemos para `"projects"`/`"system"`/`"primary"`).

O ciclo seguinte (ver "Catálogo estático de navegação" abaixo) **não
depende** de `DumpScriptingApi` — usa reflection estática direta sobre os
tipos já alcançáveis a partir de `projects`/`projects.primary`.

---

## Catálogo estático de navegação (2026-07-23)

Reflection estática adicional (mesma técnica: `Assembly.ReflectionOnlyLoadFrom`,
nenhum código executado), agora com foco no grafo de tipos alcançável a
partir de `ScriptProjects` (tipo real do global `projects`) e `IScriptProject`
(interface por trás de `projects.primary`). Ferramenta persistida:
`tools/static-api-catalog.ps1` (catálogo bruto) +
`tools/build-static-api-catalog.py` (classificação). Artefatos gerados em
`workspace/analysis/static-api/` (gitignored — regenerável a qualquer momento
rodando os dois comandos acima).

### Descoberta principal: `ScriptEngine3` é um assembly-núcleo separado

As interfaces `IScriptProject`, `IScriptTreeObject`, `IScriptObject`,
`IScriptTextDocument`, `IScriptObjectWithTextualDeclaration`/
`...Implementation`, `IScriptPouObjectCollection` e o enum `PouType` vivem
todos em **`ScriptEngine3.dll`** (não em `ScriptDriverProjects.plugin.dll`
nem `ScriptEngine.plugin.dll`) — um assembly-núcleo compartilhado entre
drivers. Isso explica por que `LogCallback`/`DriverFilter` não foram
encontrados antes: também devem estar aqui ou em assembly irmão (não
confirmado ainda, baixa prioridade).

### `ScriptProjects` (tipo real do global `projects`)

Assembly `ScriptDriverProjects.plugin` v4.1.0.0, classe não-pública (mas
exposta ao script via campo estático `Instance`):

```text
propriedades:
  primary : IExtendedObject<IScriptProject>          [CONFIRMADO em runtime]
  all     : IList<IExtendedObject<IScriptProject>>   [evidência estática — TODOS os projetos abertos]
métodos (todos write/create — NÃO usar nesta fase):
  create(path, bPrimary), open(...) [3 overloads], open_archive(...) [4 overloads],
  get_by_path(path)  [ambíguo: pode abrir se não carregado — tratado como unknown],
  convert(...) [2 overloads]
campo estático:
  Instance : ScriptProjects
```

### `IScriptProject` (interface de `projects.primary`)

Assembly `ScriptEngine3` v4.1.0.0, implementa `IScriptTreeObject` +
`IBaseObject<IScriptProject>` + `IEquatable<...>`:

```text
propriedades (sem setter, exceto onde indicado):
  dirty : bool
  primary : bool
  library : bool
  path : string                                       [CONFIRMADO em runtime]
  active_application : IExtendedObject<IScriptObject>  [TEM setter — write_candidate]
métodos (todos write/export — NÃO usar nesta fase):
  close(), save(), save_as(path,password), save_archive(path),
  document(objects) [2 overloads], export_xml(...), import_xml(...)
```

`active_application` é a rota estática para o objeto "aplicação" (o que
`06_compile_project.py`/`ScriptApplication` provavelmente precisarão) — não
testado em runtime ainda.

### `IScriptTreeObject` (implementada por `IScriptProject` E `IScriptObject`) — A API DE NAVEGAÇÃO REAL

```text
propriedades (sem setter):
  project : IExtendedObject<IScriptProject>   (referência de volta ao projeto)
  handle : int
  is_root : bool
métodos:
  find(String[] names) -> IList<IExtendedObject<IScriptObject>>
  find(String name, Boolean recursive) -> IList<IExtendedObject<IScriptObject>>
  get_children(Boolean recursive) -> IList<IExtendedObject<IScriptObject>>
```

**`get_children` existe de verdade — mas exige um argumento booleano
(`recursive`), não é chamado sem parênteses/args como o `tree_walker.py`
antigo presumia por acaso ter acertado o nome.** `find` também é um método
com parâmetros, não uma propriedade. Nenhum desses foi confirmado em
runtime ainda — permanecem `unknown` até um probe autorizado.

### `IScriptObject` (o que `get_children`/`find` devolvem)

Assembly `ScriptEngine3`, implementa `IScriptTreeObject` também:

```text
propriedades (sem setter):
  type : Guid
  guid : Guid
  embedded_object_types : IList<Guid>
  index : int
  is_folder : bool
  parent : object    (tipo fraco — não confiar sem confirmação)
métodos:
  get_name(Boolean resolve_localized_display_name) -> string
  rename(stNewName), remove(), move(new_parent, new_index) [write — NÃO usar]
  export_xml(...), import_xml(...) [write — NÃO usar]
```

`ScriptApplication` (já conhecido) implementa `IScriptApplication`/2/3/4 +
`IScriptApplicationMarker` — a cadeia exata até `IScriptObject`/
`IScriptTreeObject` não foi confirmada (não checamos se `IScriptApplication`
estende `IScriptObject`; baixa prioridade, `active_application` já dá o
tipo `IScriptObject` diretamente).

### Textual — confirma o desenho ORIGINAL de `object_reader.py`

```text
IScriptTextualObjectMarker:
  has_textual_declaration : bool
  has_textual_implementation : bool

IScriptObjectWithTextualDeclaration (estende o marker acima):
  textual_declaration : IScriptTextDocument

IScriptObjectWithTextualImplementation (estende o marker acima):
  textual_implementation : IScriptTextDocument

IScriptTextDocument:
  text : string | length : int | linecount : int          [leitura]
  get_line(n), get_text(...)                                [leitura]
  replace(...), replace_line(...), insert(...), append(...), remove(...)  [escrita]

PouType (enum): Program, FunctionBlock, Function
```

Isto bate **exatamente** com o padrão já implementado em
`common/object_reader.py` (`has_textual_declaration`/`textual_declaration`/`.text`)
— escrito antes desta rodada de reflection, por analogia com convenções
CODESYS conhecidas, e agora **confirmado por evidência estática real**.

### Achado técnico: por que `dir()` falha em `ExtendedObject<T>`

`_3S.CoDeSys.ScriptEngine.ExtendedObject`1` (assembly `ScriptEngine.plugin`)
implementa **`System.Dynamic.IDynamicMetaObjectProvider`** — o protocolo de
binding dinâmico do DLR. Tem um campo privado `BASE_OBJECT : T` (o objeto
real envolto, aqui `T = IScriptProject`) e um método `GetMetaObject(Expression)`
que intercepta o acesso a membros e os encaminha dinamicamente para
`BASE_OBJECT`. **Isto confirma a hipótese anterior**: `.path` funciona porque
IronPython usa o protocolo `IDynamicMetaObjectProvider` para resolver o
acesso (encaminhado para `BASE_OBJECT.path`), enquanto `dir()` não enumera
esse encaminhamento dinâmico — `BASE_OBJECT`/`EXTENSIONS` são privados, então
não há nada "estático" para `dir()` listar. **Não foi feito unwrap em
runtime** (fora de escopo desta rodada); o objetivo aqui era só entender o
mecanismo, que agora está documentado.

### Artefatos gerados

```text
workspace/analysis/static-api/
├── raw-catalog.json                       (saída bruta de tools/static-api-catalog.ps1)
├── reachable-types.json / .md             (catálogo classificado completo)
├── project-navigation-candidates.json     (membros relacionados a navegação)
├── text-access-candidates.json            (membros relacionados a texto de POU)
├── creation-candidates.json               (candidatos de escrita/criação)
├── compilation-candidates.json            (candidatos de compilação)
└── safety-classification.md               (tabela de TODOS os membros classificados)
```

Regenerar a qualquer momento (sem tocar o MasterTool):
```bash
powershell -File tools/static-api-catalog.ps1
python tools/build-static-api-catalog.py
```

### Cadeia mínima confirmada + candidata (objetivo do ciclo)

```text
projects (ScriptProjects, CONFIRMADO runtime)
  .primary (CONFIRMADO runtime, tipo ExtendedObject[IScriptProject])
    .path (CONFIRMADO runtime)
    .is_root (CONFIRMADO runtime — ver seção abaixo)
    .handle (CONFIRMADO runtime — ver seção abaixo)
    .active_application (candidato, static apenas)
    .get_children(recursive: bool) (candidato, static apenas — precisa de 1 arg)
    .find(name, recursive) (candidato, static apenas)
  objeto filho (IScriptObject, static apenas)
    .get_name(resolve_localized: bool) / .type / .guid / .is_folder (candidatos)
    .has_textual_declaration / .textual_declaration.text (candidatos)
```

---

## Runtime confirmado — probe de navegação (2026-07-23, `probes/03_project_navigation.py`)

Execução real contra `ExemploPlanta V1.0.project` (cópia, sem online). Escopo:
baseline `projects.primary` (não retestado) + 2 novos probes, ambos
membros de `IScriptTreeObject` (herdados por `IScriptProject`), zero
parâmetros, zero escrita. Relatório completo:
`workspace/logs/2026-07-23_11-25-13_03_probe_project_navigation/` (`report.json`,
`report.md`, `checksums.sha256` — verificados, íntegros).

| Membro | Estado | Valor | Tipo Python/IronPython | Duração |
|--------|--------|-------|------------------------|---------|
| `is_root` | **confirmed** | `True` | `bool` | 2 ms |
| `handle` | **confirmed** | `0` | `int` | 0 ms |

**Ambos confirmados** — corresponde ao cenário "Ambos confirmados" previsto:
isso comprova que o wrapper dinâmico (`ExtendedObject<IScriptProject>`)
encaminha corretamente propriedades **herdadas** de `IScriptTreeObject`
(não só as declaradas diretamente em `IScriptProject`, como `.path`). O
projeto aberto é a raiz da árvore (`is_root = True`), como esperado.

**Achado colateral (limitação do próprio probe, não do MasterTool):**
`dotnet_return_type` (via `value.GetType().FullName`) veio `None` para os
dois membros, apesar de `python_type_observed` ter funcionado (`bool`/`int`).
Hipótese: valores primitivos (bool/int) retornados por propriedades .NET são
convertidos pelo IronPython em objetos Python nativos que não expõem
`.GetType()` da mesma forma que objetos CLR complexos (o próprio
`projects.primary`, por exemplo, mostra `ExtendedObject[IScriptProject]` sem
precisar de `.GetType()`). Não investigado a fundo — `_dotnet_runtime_type()`
em `probes/03_project_navigation.py` captura a exceção mas não registra a
mensagem; correção possível para uma próxima rodada, não bloqueante.

`handle = 0`: valor único desta execução, não comparado entre execuções —
**não usar como identificador persistente** até confirmar estabilidade (ver
`handle_details.stability_note` no relatório).

### Membros promovidos à whitelist compartilhada

Com a confirmação acima, `is_root` e `handle` foram promovidos de
"whitelist autocontida do probe" para `common/capabilities.py:
CAPABILITY_PROBES["project"]` (agora `["path", "is_root", "handle"]`),
disponíveis para uso por outros scripts que já usam essa whitelist
(ex.: `02_dump_api_surface.py`).

### Próximo probe candidato (ainda não autorizado)

Conforme previsto no cenário "ambos confirmados": `active_application`,
`type`, `guid` — aguardando nova rodada de aprovação explícita antes de
qualquer execução.

---

## Runtime confirmado — probe de identidade/aplicação (2026-07-23, `probes/04_project_identity.py`)

Execução real contra `ExemploPlanta V1.0.project` (cópia, sem online). Escopo:
baseline `projects.primary` (reutilizado) + 3 probes isolados via `getattr`.

| Membro | Estado | Observação |
|--------|--------|------------|
| `type` | **unsupported** | `AttributeError` — confirma que `IScriptProject` NÃO implementa `IScriptObject` (nem a classe concreta) |
| `guid` | **unsupported** | idem |
| `active_application` | **confirmed** | retorna objeto tipo `_3S.CoDeSys.ScriptDriverProjects.ScriptObject` (classe concreta nova, wrapper `ExtendedObject[IScriptObject]`) |

**Achado incidental valioso**: a saída bruta do MasterTool (via o `ToString()`
do objeto — ver "Correção de política" abaixo) revelou, sem qualquer chamada
adicional deliberada: `Name=Application`, `guid=00000000-0000-0000-0000-000000000001`.
Esse GUID **bate exatamente** com o nome do arquivo
`ExemploPlanta V1.0.Device.Application.00000000-0000-0000-0000-000000000001.compileinfo`
observado na pasta do projeto no início desta investigação — evidência cruzada
independente e forte de que esse GUID específico é estável.

```text
persistence_status: strongly_indicated
evidence:
  - runtime value (via ToString() do objeto retornado)
  - matching compileinfo filename (observação independente, início da sessão)
```

Ainda **não confirmado como estável entre execuções** (exigiria fechar/reabrir
o MasterTool e reabrir o mesmo projeto — não realizado, não necessário agora).

### Correção de política — serialização estrita (2026-07-23)

A primeira versão de `probes/04_project_identity.py` registrava uma
"representação segura" de `active_application` usando `repr(value)` do
Python. **Em IronPython, `repr()`/`str()` sobre um objeto `.NET` tipicamente
invoca `ToString()`** — uma CHAMADA DE MÉTODO na instância, fora do escopo
aprovado para aquela execução ("proibido chamar métodos no objeto
retornado"). `ToString()` é só convenção do `.NET` (documentado, mas não uma
garantia técnica); uma classe pode sobrescrevê-lo com qualquer efeito.

Classificação do desvio (não invalida o resultado principal):
```text
capability_state: confirmed
property_access: compliant
post_access_stringification: policy_deviation
side_effect_observed: false
result_validity: accepted_with_serialization_caveat
```

**Corrigido**: a política de serialização agora vive centralizada em
`common/capabilities.py` (`build_representation()`, `python_type_info()`,
`dotnet_type_info()`, `strict_object_repr()`), reutilizável por todos os
scripts de probe. Regra: **nunca** `repr()`/`str()`/`.ToString()`/formatação
implícita em objetos `.NET` desconhecidos — só serializa o valor quando é
primitivo Python nativo ou um tipo `.NET` **confirmado** (via `GetType()`,
não suposição) como seguro (`System.String`/`System.Guid`/numéricos — value
types selados da BCL, `ToString()` documentado e não sobrescrevível).
Qualquer outro tipo vira representação `type_only` (`<NomeDoTipo>`), montada
só do nome do tipo. Testes: `tests/unit/test_strict_representation.py`
(inclui um objeto sintético cujo `__repr__`/`__str__` levantam exceção, para
provar que nunca são chamados em tipos desconhecidos).

### Incidente operacional (não relacionado à API): perda e reconstrução de artefatos

Durante a correção acima, um comando de limpeza (`rm -rf` com glob por
sufixo) apagou por engano os artefatos ORIGINAIS desta execução real
(`report.json`/`report.md`/`checksums.sha256`). Classificação de
proveniência (obrigatória a partir de 2026-07-23):

```text
report.json:       provenance: reconstructed_from_captured_output | original_runtime_artifact: false
report.md:         provenance: regenerated_from_reconstructed_json | original_runtime_artifact: false
checksums.sha256:  validates: reconstructed_files_only
```

`report.json` foi reconstruído byte a byte a partir do conteúdo já capturado
na conversa; `report.md` foi regenerado (conteúdo equivalente, formatação
não garantidamente idêntica); `checksums.sha256` foi recalculado sobre os
arquivos reconstruídos — **não prova identidade com os arquivos apagados**,
só que os reconstruídos não mudaram desde a reconstrução. A capacidade
`active_application` permanece válida: o acesso foi observado no MasterTool
real, o tipo retornado foi registrado durante a execução original, não
houve erro no getter, e a reconstrução ocorreu depois da execução. Detalhe
completo em
`workspace/logs/2026-07-23_11-34-20_04_probe_project_identity/POLICY-DEVIATION-NOTE.md`.

**Proteção permanente adicionada**: `scripts/maintenance/safe_clean_artifact.py`
(lógica em `src/mastertool_bridge/utils/safe_cleanup.py`) — recusa glob,
caminho vazio, caminho fora de `workspace/`, remoção de `workspace/logs`
inteiro, e exige um arquivo sentinela (`.mastertool-bridge-run`, gravado
automaticamente por `common/file_io.new_export_dir` em todo diretório de
execução) antes de permitir a remoção. Modo dry-run é o padrão; remoção real
exige `--confirm` explícito. Testes: `tests/unit/test_safe_cleanup.py` (15
casos, incluindo os 6 cenários obrigatórios: glob bloqueado, caminho fora de
workspace bloqueado, `workspace/logs` inteiro bloqueado, caminho vazio
bloqueado, diretório sem sentinela bloqueado, diretório exato válido
permitido só com confirmação). Até esta proteção existir, nenhuma limpeza
automática era feita sobre artefatos reais de runtime.

### Reorganização: probes/ separados dos scripts funcionais

Para evitar colisão de numeração com os scripts funcionais planejados
(`04_export_project.py`, `05_export_selected_object.py`, ...), os scripts
exploratórios foram movidos para `scripts/mastertool/probes/` em 2026-07-23:

```text
scripts/mastertool/probes/
├── 02_dump_official_scripting_api.py   (era 02_dump_official_scripting_api.py na raiz)
├── 03_project_navigation.py            (era 03_probe_project_navigation.py na raiz)
├── 04_project_identity.py              (era 04_probe_project_identity.py na raiz)
└── 05_children_collection.py           (novo, criado direto na subpasta)
```

`00_smoke_test.py`, `01_discover_environment.py` e `02_dump_api_surface.py`
(o verificador de superfície conhecida — distinto do dumper oficial)
permanecem na raiz de `scripts/mastertool/`, como ferramentas permanentes da
Fase 0. O bootstrap de cada script movido foi ajustado (`sys.path` aponta
para `scripts/mastertool/`, não para a própria pasta `probes/`, já que
`common/` vive um nível acima). Ao mover `probes/03_project_navigation.py`,
também foi corrigida uma violação de política latente idêntica à de
`04_project_identity.py` (uma função local chamava `str(value)` em qualquer
valor não bool/int/float — nunca se manifestou porque `is_root`/`handle`
sempre retornaram primitivos, mas o código tinha o mesmo defeito).

### Membro promovido à whitelist compartilhada

`active_application` promovido para `common/capabilities.py:
CAPABILITY_PROBES["project"]` (agora `["path", "is_root", "handle",
"active_application"]`). `type`/`guid` **não** promovidos (unsupported).

### Próximo probe autorizado: primeira chamada de método de navegação

```python
projects.primary.get_children(False)
```

Script: `scripts/mastertool/probes/05_children_collection.py`. Escopo: uma
única chamada, sem iteração dos elementos, sem stringificar a coleção nem
seus elementos; só registra o tipo da coleção (via `GetType()`) e `.Count`
(membro padrão de `ICollection<T>`/`IList<T>` da BCL, não do catálogo
customizado).

---

## Runtime confirmado — probe de coleção de filhos (2026-07-23, `probes/05_children_collection.py`)

Execução real contra `ExemploPlanta V1.0.project` (cópia, sem online). Uma
única chamada `project.get_children(False)`, sem iteração, sem
stringificação. Relatório completo:
`workspace/logs/2026-07-23_13-43-14_05_children_collection/` (`report.json`,
`report.md`, `checksums.sha256` — verificados, íntegros, inclui o arquivo
sentinela `.mastertool-bridge-run`).

| Campo | Valor |
|-------|-------|
| `get_children(False)` | **confirmed**, 1 chamada, 5 ms |
| Tipo .NET real da coleção | `System.Collections.Generic.List<IExtendedObject<IScriptObject>>` (concreto, não apenas a interface `IList<T>` declarada) |
| Implementa ICollection/IList (via `GetType().GetInterfaces()`) | **True** — confirmado antes de tentar `Count` |
| `Count` | **confirmed**, valor = **4**, 0 ms |
| Iteração realizada | False |
| Stringificação da instância realizada | False (representação `type_only`) |

**Marco alcançado**: a cadeia mínima de navegação está confirmada de ponta a
ponta:

```text
projects (ScriptProjects, CONFIRMADO)
  .primary → IExtendedObject<IScriptProject> (CONFIRMADO)
    .path (CONFIRMADO) | .is_root (CONFIRMADO) | .handle (CONFIRMADO)
    .active_application → IExtendedObject<IScriptObject> (CONFIRMADO)
    .get_children(False) → List<IExtendedObject<IScriptObject>>, Count=4 (CONFIRMADO)
```

`ExemploPlanta V1.0.project` tem **4 objetos de topo** diretamente sob o
projeto.

---

## Runtime confirmado — probe de identidade do primeiro filho (2026-07-23, `probes/06_first_child_identity.py`)

Execução real contra `ExemploPlanta V1.0.project` (cópia, sem online).
`get_children(False)` → `Count=4` → `children[0]` (indexador nativo, único
índice acessado) → 4 probes isolados de identidade. Relatório completo:
`workspace/logs/2026-07-23_13-51-34_06_first_child_identity/` (`report.json`,
`report.md`, `checksums.sha256` — verificados, íntegros, inclui sentinela).

| Membro | Estado | Valor |
|--------|--------|-------|
| `is_folder` | confirmed | `False` |
| `type` | confirmed | GUID `8753fe6f-4a22-4320-8103-e553c4fc8e04` (tipo confirmado `System.Guid`) |
| `guid` | confirmed | GUID `00000000-0000-0000-0000-000000000144` (tipo confirmado `System.Guid`, `persistence_status: unverified`) |
| `get_name(False)` | confirmed | `"Project Settings"` |

**Tipo .NET real do primeiro filho**: `_3S.CoDeSys.ScriptDriverProjects.ScriptObject`
— a MESMA classe concreta que já vimos por trás de `active_application`
(probe anterior). Confirma que filhos da árvore e a Application são
instâncias do mesmo tipo concreto, ambos por trás da interface `IScriptObject`.

**`type` vs `guid` são GUIDs distintos, como esperado**: `type` parece
identificar a ESPÉCIE do objeto (ex.: "isto é uma pasta de configurações"),
`guid` identifica esta INSTÂNCIA específica — hipótese, não confirmada além
da observação de que os valores diferem.

**Achado sobre o primeiro filho**: `ExemploPlanta V1.0.project` tem um objeto
de topo chamado **"Project Settings"** (não é a Application — essa foi
alcançada antes por um caminho diferente, `active_application`). Os outros
3 dos 4 objetos de topo ainda não foram identificados.

### Achado colateral: limitação do campo `value` em `get_name(False)`

`get_name_false.value` saiu `null` no relatório, apesar do nome real
("Project Settings") estar corretamente capturado em
`get_name_false.representation.value` (modo `"value"`, sem stringificação da
instância — 100% seguro). Causa: o script só preenchia o campo de
conveniência `value` quando `dotnet_type.full_name == "System.String"`, mas
`dotnet_type.available` veio `False` para essa string nativa do IronPython —
mesma peculiaridade já observada com `is_root`/`handle` (primitivos nativos
não respondem a `GetType()` de forma confiável neste host, mesmo sendo
apoiados por tipos .NET). Não é um problema da política de serialização
(`build_representation()` funcionou corretamente); é uma checagem
excessivamente conservadora no campo `value` específico deste script. Os
dados reais permanecem íntegros e acessíveis via `representation.value` em
todos os probes já executados.

### Correção de política de serialização (2a rodada) — 2026-07-23

O achado colateral acima (`get_name_false.value == null`) tinha DUAS causas
sobrepostas: (1) `build_representation()` só reconhecia `str`, perdendo
`unicode` (peculiaridade do IronPython 2.7); (2) o script 06 tinha uma
checagem redundante exigindo `dotnet_type.full_name == "System.String"`
para preencher o campo de conveniência `value` — mas primitivos nativos não
respondem a `GetType()` de forma confiável neste host. Corrigido em
`common/capabilities.py` via `_STRING_TYPES` (`basestring`/`str`, nunca via
`GetType()`); `build_representation()` passou a expor `value_available`/
`serialization_mode` além dos campos originais. Testes ampliados em
`tests/unit/test_strict_representation.py`. O probe 07 (abaixo) já usa a
versão corrigida e confirma que o campo `value` vem preenchido corretamente.

### Probe dos 3 elementos de topo restantes executado — 2026-07-23

`probes/07_remaining_top_level_children.py`, contra `ExemploPlanta V1.0.project`
real. Pré-condição obrigatória confirmada primeiro: `get_children(False)`
**confirmed** (1 chamada) e `Count == 4` **confirmed** (bate exatamente com o
esperado — nenhum indício de mudança estrutural desde os probes 05/06).
Acesso via tupla fixa `AUTHORIZED_INDICES = (1, 2, 3)`, indexador nativo,
sem iteração da coleção. Relatório em
`workspace/logs/2026-07-23_14-08-02_07_remaining_top_level_children/`,
checksums verificados (`sha256sum -c` → 3/3 `OK`), 0 erros.

Resultado: **todos os 12 probes de identidade (4 por índice × 3 índices)
confirmed**, sem exceções, sem stringificação de instância desconhecida
(`instance_stringification_performed: false` em todos — só `type`/`guid`
usaram `confirmed_dotnet_type` após `GetType()` confirmar `System.Guid`).

| Índice | Nome (`get_name(False)`) | `is_folder` | `type` (GUID) | `guid` (GUID) | Tipo .NET concreto |
|--------|---------------------------|-------------|---------------|---------------|---------------------|
| 0 (lido no probe 06) | "Project Settings" | `False` | `8753fe6f-4a22-4320-8103-e553c4fc8e04` | `00000000-0000-0000-0000-000000000144` | `_3S.CoDeSys.ScriptDriverProjects.ScriptObject` |
| 1 | **"Device"** | `False` | `225bfe47-7336-4dbc-9419-4105a7c831fa` | `00000000-0000-0000-0000-000000000208` | `_3S.CoDeSys.ScriptDriverProjects.ScriptObject` |
| 2 | **"Project Information"** | `False` | `085afe48-c5d8-4ea5-ab0d-b35701fa6009` | `00000000-0000-0000-0000-000000000106` | `_3S.CoDeSys.ScriptDriverProjects.ScriptObject` |
| 3 | **"__VisualizationStyle"** | `False` | `8e687a04-7ca7-42d3-be06-fcbda676c5ef` | `00000000-0000-0000-0000-000000000137` | `_3S.CoDeSys.ScriptDriverProjects.ScriptObject` |

Achados:
- Os 4 objetos de topo de `ExemploPlanta V1.0.project` estão agora TODOS
  integralmente identificados (nome, `is_folder`, `type`, `guid`):
  **Project Settings, Device, Project Information, __VisualizationStyle**
  — nenhum é uma "pasta" (`is_folder=False` em todos os 4); nenhum é a
  Application (alcançada por caminho distinto via `active_application`).
- Os 4 valores de `type` (GUID) são todos DIFERENTES entre si — ou seja,
  cada um destes 4 nós é de uma ESPÉCIE distinta de objeto (reforça a
  hipótese de que `type` identifica a espécie/classe do objeto, não é um
  valor fixo compartilhado por todo objeto de topo).
- Tipo .NET concreto idêntico nos 4 (`_3S.CoDeSys.ScriptDriverProjects.ScriptObject`)
  — confirma que a MESMA classe concreta representa objetos de topo
  semanticamente muito diferentes (configuração, device, metadado,
  estilo de visualização); a diferenciação semântica vem de `type`
  (GUID), não do tipo .NET do wrapper.
- Campo de conveniência `value` de `get_name(False)` veio preenchido
  corretamente nos 3 (`serialization_mode: "native_string"`,
  `value_available: true`) — confirma que a correção de política resolveu
  o achado colateral do probe 06.

### Critério de reativação do `tree_walker.py` — 5 de 5 CONFIRMADOS

```text
1. um membro que retorne os objetos raiz ou filhos       [CONFIRMADO: get_children(False)]
2. tipo real da coleção retornada                        [CONFIRMADO: List<IExtendedObject<IScriptObject>>]
3. forma segura de iterar                                [CONFIRMADO: acesso por índice (0..3) via indexador nativo, sem GetEnumerator()/iter(), Count sempre lido e validado antes]
4. nome e tipo de cada nó                                [CONFIRMADO: 4 de 4 nós de topo identificados (Project Settings/Device/Project Information/__VisualizationStyle), todos com type/guid/is_folder]
5. ausência de efeitos colaterais durante a leitura       [CONFIRMADO: 0 erros, 0 exceções, nenhuma escrita/compilação/navegação online em nenhum dos 4 acessos, projeto seguiu íntegro]
```

Os 5 critérios estão atendidos. Isso justificou propor um `ProjectTreeAdapter`
LIMITADO — **aprovado pelo usuário em 2026-07-23**, com dois ajustes:
correção dos dados do índice 0 (abaixo) e separação entre `Count`
observado e `expected_count` opcional (ver seção seguinte). **`tree_walker.py`
genérico continua suspenso** e só deve ser reativado após aprovação
explícita separada; a existência do adapter não o reativa por si só.

### `ProjectTreeAdapter` implementado — 2026-07-23

`common/project_tree_adapter.py`: snapshot limitado dos filhos diretos de
um projeto já resolvido, profundidade fixa em no máximo 1
(`MAX_SUPPORTED_DEPTH = 1`; não existe parâmetro `recursive` — profundidade
maior nunca é uma opção aceita, nem convertida internamente).

Decisão de design importante (correção pedida pelo usuário sobre a
proposta original): `Count` observado na execução é sempre o limite real
da enumeração — pertence ao PROJETO, não à API do MasterTool.
`expected_count` é um parâmetro OPCIONAL, usado só para validação
específica de um projeto/teste conhecido (ex.: `expected_count=4` para
`ExemploPlanta V1.0.project`); quando fornecido e divergente do valor
observado, fica registrado (`collection.count_matches_expected: false` +
uma entrada informativa em `errors`), mas **não interrompe a enumeração**
— adicionar um objeto legítimo ao projeto não deve virar falha permanente
da API. `max_children` (`DEFAULT_MAX_CHILDREN = 64`) continua sendo um
teto rígido de segurança: `Count` negativo ou maior que `max_children`
ABORTA o snapshot (não há como estabelecer um limite de enumeração
confiável nesses casos).

Granularidade de falha:
- falha em `get_children(False)` ou em `Count` → aborta o snapshot inteiro;
- falha no acesso a um índice (`children[i]`) → interrompe a enumeração
  NAQUELE ponto (nenhum índice seguinte é tentado), mas os nós já lidos
  com sucesso ANTES da falha permanecem no resultado;
- falha isolada em `name`/`is_folder`/`type`/`guid` de UM nó → não aborta
  nada; fica registrada como estado por campo
  (`{"state": ..., "value": None, "error": ...}"`) e o processamento
  continua para os demais campos/nós.

Saída 100% serializável (dict/list/str/int/float/bool/None) — nunca inclui
o proxy do ScriptEngine, `ExtendedObject`, a coleção CLR ou qualquer
referência viva. Uma função auxiliar (`render_simplified_snapshot()`)
produz uma visão achatada (só os valores, sem o estado por campo) para
relatórios/consumo rápido — nunca é a fonte de verdade.

21 testes com fakes em memória (sem MasterTool real) em
`tests/unit/test_project_tree_adapter.py`, cobrindo: coleção vazia, 1/4
elementos, `Count` negativo, `Count` maior que `max_children`, `Count`
divergente de `expected_count` (não aborta), falha em `get_children`/
`Count`/indexador (aborta), falha isolada em cada campo de identidade
(não aborta), garantia de chamada única por membro, garantia de que a
coleção nunca é iterada, garantia de que nenhum proxy aparece no
resultado, objeto com `__repr__`/`__str__` explosivos tratado com
segurança, e recusa de profundidade > 1 sem tocar no projeto.

`probes/08_validate_root_adapter.py` criado para validar o adaptador
contra o projeto real (`expected_count=4`, `max_children=16`). Dry-run
fora do MasterTool confirma degradação graciosa.

### `ProjectTreeAdapter` validado em runtime real — 2026-07-23

Execução real de `probes/08_validate_root_adapter.py` contra
`ExemploPlanta V1.0.project`, checksums verificados (`sha256sum -c` → 3/3
`OK`). Resultado: `collection.state=confirmed`, `count=4`,
`count_matches_expected=true`, `complete=true`, **0 erros** em
`snapshot["errors"]`.

Os 4 nós retornados pelo `simplified.children` batem EXATAMENTE (nome,
`is_folder`, `type_guid`, `object_guid` — GUID por GUID) com os já
confirmados isoladamente nos probes 06/07:

| Índice | Nome | `type_guid` | `object_guid` |
|--------|------|-------------|----------------|
| 0 | Project Settings | `8753fe6f-4a22-4320-8103-e553c4fc8e04` | `00000000-0000-0000-0000-000000000144` |
| 1 | Device | `225bfe47-7336-4dbc-9419-4105a7c831fa` | `00000000-0000-0000-0000-000000000208` |
| 2 | Project Information | `085afe48-c5d8-4ea5-ab0d-b35701fa6009` | `00000000-0000-0000-0000-000000000106` |
| 3 | __VisualizationStyle | `8e687a04-7ca7-42d3-be06-fcbda676c5ef` | `00000000-0000-0000-0000-000000000137` |

`root.path` (caminho real do `.project` aberto) e `root.is_root=true`
também confirmados. Isto valida que o adaptador reproduz fielmente, de
forma genérica e reutilizável, o mesmo dado antes obtido por scripts de
probe individuais — primeiro consumidor real e auditado da cadeia de
navegação confirmada. `tree_walker.py` genérico segue suspenso.

### Decisão: próximo nó a testar é Device, não active_application — 2026-07-23

`active_application` é um atalho direto fornecido pelo projeto — não prova
que a descida pela árvore funciona de forma GENÉRICA (pelo mesmo caminho
que qualquer outro nó usaria). `Device` (`root_children[1]`, já
identificado nos probes 06/07/08) foi escolhido para o primeiro teste de
navegação em 2 níveis, porque exige repetir a MESMA cadeia já confirmada
no primeiro nível (`get_children(False)` → `Count` → indexador), mas
partindo de um nó filho em vez da raiz:

```text
projects.primary
└── Device
    └── get_children(False)
```

`active_application` continua reservado para uma confirmação cruzada
posterior (comparar o GUID de um filho de `Device` com o GUID de
`active_application` — se baterem, confirma que o caminho hierárquico via
`Device` chega ao mesmo objeto que o atalho `active_application`).

### `probes/09_device_children_collection.py` criado — 2026-07-23

Primeiro teste de navegação hierárquica REAL em 2 níveis. Antes de tocar
em `device.get_children(False)`, o script REVALIDA (nesta mesma execução,
sem reaproveitar dados de probes anteriores):
- `root_children.Count == 4` (senão aborta como `root_count_mismatch`, sem
  acessar `root_children[1]`);
- `root_children[1].get_name(False) == "Device"`;
- `root_children[1].type == 225bfe47-7336-4dbc-9419-4105a7c831fa`;
- `root_children[1].guid == 00000000-0000-0000-0000-000000000208`.

Qualquer divergência nessas 3 identidades registra `device_identity_mismatch`
e ENCERRA sem chamar `device.get_children(False)`. Só com a identidade
confirmada o script chama `device.get_children(False)` (1 vez) e, na
coleção retornada: verifica nulidade, registra tipo Python/.NET (via
`build_representation()`, sem `repr()`/`str()`/`ToString()`), confirma via
`GetType().GetInterfaces()` se implementa `ICollection`/`IList`, e — só se
confirmado — lê `Count` uma única vez. Não indexa, não itera, não lê
nomes dos filhos de `Device` nesta execução. `Count` dos filhos de Device
não tem valor esperado fixo (`expected_root_count=4` só se aplica à raiz);
`Count < 0` ou `Count > max_device_children` (64) são marcados inválidos
sem abortar o restante do relatório; `Count == 0` é um resultado válido
(coleção vazia).

Validado EXTERNAMENTE (fora do MasterTool, com fakes em memória — 7
cenários, não persistido como teste automatizado do repositório):
sucesso total (identidade bate, `Count` no meio do intervalo válido),
`root_count_mismatch` (aborta sem acessar índice 1), `device_identity_mismatch`
(nome errado — aborta sem chamar `device.get_children`), `Count == 0`
(válido), `Count < 0` (inválido), `Count > 64` (inválido, limite de
segurança), coleção sem interface `ICollection`/`IList` confirmada
(`Count` nunca tentado). Todos os 7 cenários se comportaram exatamente
como especificado.

### Navegação em 2 níveis confirmada em runtime real — 2026-07-23

Execução real de `probes/09_device_children_collection.py` contra
`ExemploPlanta V1.0.project`, checksums verificados (`sha256sum -c` → 3/3
`OK`). Resultado, **0 erros**:

- Revalidação de identidade de `Device` (`root_children[1]`): `name`,
  `type`, `guid` todos `confirmed` e batendo com os valores esperados
  (`matches_expected: true` nos 3) — a identidade foi confirmada de novo
  nesta execução, não reaproveitada dos probes 06/07/08.
- `device.get_children(False)` **confirmed** — tipo .NET concreto do
  retorno **IDÊNTICO** ao da coleção da raiz:
  `System.Collections.Generic.List<IExtendedObject<IScriptObject>>`
  (mesmo genérico `ScriptEngine3, Version=4.1.0.0` visto na raiz).
- `GetType().GetInterfaces()` confirma 8 interfaces, incluindo as
  variantes genéricas de `IList`, `ICollection`, `IReadOnlyList` e
  `IReadOnlyCollection` — o mesmo padrão observado na coleção da raiz.
- `device_children.Count` **confirmed** = **2**, validado (não negativo,
  dentro de `max_device_children=64`).

**Marco**: a MESMA cadeia de navegação (`get_children(False)` → `Count`
via `GetType().GetInterfaces()` → indexador nativo) funciona identicamente
partindo de um nó FILHO (`Device`), não só da raiz — primeira prova
concreta de que a descida pela árvore é GENÉRICA, não um comportamento
especial de `projects.primary`. `Device` tem exatamente 2 filhos diretos
(ainda não identificados — nenhum foi indexado/lido nesta execução, por
desenho).

### `probes/10_device_first_child_identity.py` criado — 2026-07-23

Próximo passo aprovado: identificar SOMENTE o primeiro filho de `Device`
(`device_children[0]`), sem acessar `active_application` na mesma
execução (fica para outro probe — misturar agora dificultaria isolar
exatamente qual acesso causou uma eventual falha). Mantém o teste
causalmente simples:

```text
Project → Device validado → coleção de 2 filhos validada
→ Device.children[0] → identidade básica
```

Toda a lógica de segurança foi extraída para uma função PURA (sem I/O) em
`common/device_first_child_probe.py` — mesmo padrão de
`common/project_tree_adapter.py` — para ser testável com fakes em
memória. Fluxo obrigatório, cada passo só ocorre se o anterior foi
confirmado:

1. `project.get_children(False)`, 1 chamada;
2. `root_children.Count == 4` (senão aborta `root_count_mismatch`, sem
   acessar índice 1);
3. `root_children[1]`, 1 acesso por índice;
4. revalidação de identidade de Device NESTA execução (`get_name(False)`,
   `type`, `guid`, sem reaproveitar dados de probes anteriores) —
   qualquer divergência aborta `device_identity_mismatch`, SEM chamar
   `device.get_children(False)`;
5. `device.get_children(False)`, 1 chamada, só com identidade confirmada;
6. coleção não pode ser nula; deve implementar `ICollection`/`IList`;
   `Count == 2` — qualquer uma destas falhar aborta
   (`device_children_collection_null`/
   `device_children_count_interface_unconfirmed`/
   `device_children_count_mismatch`), SEM acessar índice 0;
7. `device_children[0]`, 1 acesso por índice — NUNCA índice 1, NUNCA
   iteração;
8. 4 probes ISOLADOS de identidade no primeiro filho
   (`is_folder`/`type`/`guid`/`get_name(False)`) — falha em UM não aborta
   os demais.

Restrição explícita pedida pelo usuário: para os campos `type`/`guid` do
PRIMEIRO FILHO (não para a revalidação de Device, que segue o mesmo
padrão já confirmado no probe 09), o valor só é serializado quando
`GetType()` confirma exatamente `System.Guid` — mais estrito que
`build_representation()` isolado (que também aceitaria String/Boolean/
numéricos confirmados).

16 testes PERMANENTES em `tests/unit/test_device_first_child_probe.py`
(persistidos ANTES da execução real, como pedido): sucesso completo, raiz
com `Count != 4`, identidade de Device divergente (nome e type/guid),
`Count` de Device `!= 2`, coleção sem interface de contagem, falha no
indexador 0, falha isolada em cada campo de identidade (incluindo `guid`
ausente via `AttributeError`), valor de `type`/`guid` só serializado
quando confirmado `System.Guid`, garantia de que `device_children[1]`
nunca é acessado, garantia de que `root_children` só acessa o índice 1,
garantia de que o primeiro filho nunca recebe `get_children()`, mais
falhas estruturais mais cedo na cadeia (falha em `get_children` da raiz,
coleção nula). `probes/10_device_first_child_identity.py` é um wrapper
fino sobre essa função. Dry-run fora do MasterTool confirma degradação
graciosa.

### Primeiro filho de Device identificado em runtime real — 2026-07-23

Execução real de `probes/10_device_first_child_identity.py` contra
`ExemploPlanta V1.0.project`, checksums verificados (`sha256sum -c` → 3/3
`OK`). Resultado, **0 erros**:

- `root_children.Count == 4` revalidado; identidade de `Device` revalidada
  nesta execução (`name`/`type`/`guid`, todos `confirmed` e
  `matches_expected: true`).
- `device.get_children(False)` **confirmed** — mesmo tipo .NET concreto e
  mesmas 8 interfaces do probe 09; `device_children.Count == 2`
  confirmado.
- `device_children[0]` **confirmed**. Identidade do primeiro filho, todos
  os 4 campos `confirmed`:

| Campo | Valor |
|-------|-------|
| `name` | **"Plc Logic"** |
| `is_folder` | `False` |
| `type` | `40b404f9-e5dc-42c6-907f-c89f4a517386` |
| `guid` | `00000000-0000-0000-0000-000000000177` |

O primeiro filho de `Device` **NÃO é a Application** — é um objeto
chamado "Plc Logic" (não é pasta). Por decisão já registrada: como o
índice 0 não é `Application`, o próximo probe deve acessar somente
`device_children[1]` (não comparar ainda com `active_application`).
`tree_walker.py` permanece suspenso até pelo menos a cadeia
`Project → Device → Application → filhos diretos da Application` estar
confirmada.

### Mudança de estratégia: scanner recursivo em vez de probes por índice — 2026-07-23

Depois de 6 probes confirmando a mesma cadeia de navegação um índice por
vez (05-10), decisão: **parar de criar um probe por índice/execução**.
Toda a evidência acumulada até aqui —

- `get_children(False)` funciona identicamente na raiz e em qualquer nó
  filho;
- o retorno é sempre o mesmo tipo concreto
  (`System.Collections.Generic.List<IExtendedObject<IScriptObject>>`),
  com as mesmas interfaces (`ICollection`/`IList`/`IReadOnlyList`/
  `IReadOnlyCollection`);
- `Count`, indexador nativo, `is_folder`/`type`/`guid`/`get_name(False)`
  todos confirmados em múltiplos níveis;
- um objeto com `is_folder == False` PODE ter filhos (`Device` tem 2);
- a política de serialização estrita (`build_representation()`) está
  implementada e testada —

é suficiente para generalizar a cadeia inteira numa varredura recursiva,
em vez de continuar validando um índice de cada vez.

Criado `common/read_only_project_scanner.py: ReadOnlyProjectScanner` —
scanner DFS iterativo (pilha explícita, nunca recursão Python nem
`GetEnumerator()`/`iter()`/`list()` sobre a coleção CLR), com limites
obrigatórios (`max_depth`, `max_total_nodes`, `max_children_per_node`),
isolamento de falhas por ramo (falha num nó nunca aborta outros ramos;
só o limite global de `max_total_nodes` aborta o scan inteiro, preservando
tudo já coletado), e detecção conservadora de ciclos (`object_guid`
repetido entre ANCESTRAIS do próprio nó bloqueia a descida; repetido em
ramos sem relação vira só `duplicate_object_guid` informativo — `handle`
nunca é usado como identificador). `node_id` é construído exclusivamente
pelo caminho de índices (`root/1/0`), nunca pelo GUID. Saída 100%
serializável — nenhum proxy/coleção CLR aparece no resultado.

**`tree_walker.py` NÃO foi reativado** — módulo novo e independente. Ver
especificação completa em `docs/11-read-only-project-scanner.md`.

31 testes permanentes em `tests/unit/test_read_only_project_scanner.py`
(fakes em memória, sem MasterTool real), cobrindo estrutura, navegação,
identidade, falhas, segurança e ciclos/duplicidades.
`probes/12_validate_recursive_scanner.py` criado como wrapper fino, com
limites conservadores para esta primeira validação
(`max_depth=6, max_total_nodes=2000, max_children_per_node=128,
expected_root_count=4` — este último específico de
`ExemploPlanta V1.0.project`, nunca fixado no scanner genérico). Validado
externamente: dry-run sem `projects` (degradação graciosa) e uma segunda
execução com árvore sintética via fakes espelhando exatamente a estrutura
real já confirmada (Project Settings / Device → Plc Logic + Bus /
Project Information / __VisualizationStyle) — todos os 8 artefatos
(`report.json`/`.md`, `project-tree.json`, `flat-nodes.json`,
`node-indexes.json`, `errors.json`, `checksums.sha256`, sentinela)
gerados corretamente, estatísticas (`total_nodes=7`, `scan_complete=true`,
`0` erros) e índices por nome batendo exatamente com os nomes já
confirmados em runtime real.

### Scanner recursivo validado em runtime real — SUCESSO TOTAL — 2026-07-23

Execução real de `probes/12_validate_recursive_scanner.py` contra
`ExemploPlanta V1.0.project`, checksums verificados (`sha256sum -c` → 8/8
`OK`). Resultado:

```text
total_nodes = 117
complete_nodes = 117 | partial_nodes = 0 | failed_nodes = 0
collections_read = 113 | empty_collections = 87
field_errors = 0 | collection_errors = 0 | index_errors = 0
duplicate_object_guids = 0
maximum_depth_reached = 6
scan_complete = true
```

`root.collection`: `Count == 4`, `count_matches_expected == true`.
`safety_declaration`: todas as flags de escrita/compilação/online/acesso
textual/iteração direta `false`; `read_only`, `bounded_index_navigation`
e `recursive_navigation` `true` — exatamente como esperado.

**Único limite atingido**: `max_depth_reached = true`. Os 4 nós em
**profundidade 7** (`U1_Inversor_Elevador`, `U2_Inversor_Carro`,
`U3_Inversor_Corte`, `U4_Inversor_Agitador` — parâmetros de dispositivo
sob `EtherNet_IP_Scanner`) aparecem na árvore com identidade completa,
mas tiveram a busca de filhos deliberadamente não tentada
(`collection.state = "not_attempted_depth_limit"`) — comportamento
exatamente conforme especificado, não um erro. `max_total_nodes_reached`
e `max_children_per_node_reached` ambos `false`.

**Estrutura completa descoberta** (árvore resumida; profundidade entre
parênteses):

```text
Project (ExemploPlanta V1.0.project)
├── Project Settings                        (1, folha)
├── Device                                   (1)
│   ├── Plc Logic                            (2)
│   │   └── Application                      (3, 15 filhos)
│   │       ├── Library Manager, Bill of Materials, Configuration and Consumption
│   │       ├── SystemGVLs (4) / UserGVLs (3)
│   │       ├── Task Configuration → MainTask/ENIPScannerIOTask/ENIPScannerServiceTask
│   │       ├── SystemPOUs / UserPOUs / SystemEvents
│   │       ├── FuncoesExemplo (11 FBs de aplicação: CONT_RETEN, TRAVA_SEGURANCA, ...)
│   │       ├── TiposDadosExemplo (8: Equipamento, DrivesExemplo, PrgValvulasExemplo, PrgPrgPrgParametrosExemploExemploAuxExemplo, Omron, ...)
│   │       ├── I/Os (EntradasExemplo/Saidas)
│   │       ├── PrgHookExemplo → ProgramasExemplo (11 POUs: Elevador_Vertical, Carro_Horizontal, ...)
│   │       ├── UnidadesAuxExemplo → ProgramasExemplo (7 POUs)
│   │       └── Variáveis Globais (14 GVLs de usuário)
│   └── Configuration                        (2)
│       └── NX3005                           (3, 10 filhos: rede/dispositivos)
│           └── NET 1 → Ethernet → EtherNet_IP_Scanner
│               └── U1..U4_Inversor_*        (7, LIMITE DE PROFUNDIDADE — não expandidos)
├── Project Information                      (1, folha)
└── __VisualizationStyle                     (1, folha)
```

**Confirmação cruzada Application ↔ active_application**: o nó
`root/1/0/0` ("Application", alcançado pela navegação hierárquica
GENÉRICA via `Device → Plc Logic`) tem **exatamente o mesmo
`object_guid`** (`00000000-0000-0000-0000-000000000001`) já registrado
para `active_application` desde o probe 04 — o mesmo GUID que bateu, na
época, com o arquivo `.compileinfo` observado independentemente
(`ExemploPlanta V1.0.Device.Application.7bd30f35-....compileinfo`). Isso
confirma, sem precisar de nenhum probe adicional dedicado, que:

```text
caminho hierárquico via Device (Project → Device → Plc Logic → Application)
==
atalho projects.primary.active_application
```

**Achado técnico adicional**: os nós da subárvore de hardware/rede
(`Device`, `Configuration`, `NX3005`, `NET 1`/`Ethernet`/
`EtherNet_IP_Scanner`, os 4 inversores) compartilham o MESMO `type_guid`
(`225bfe47-7336-4dbc-9419-4105a7c831fa`) — o mesmo já visto para
`Device` desde o probe 09. Reforça a hipótese de que `type` identifica
uma ESPÉCIE ampla de objeto (aqui, "nó da árvore de dispositivos"), não
um tipo por-objeto-de-negócio; os objetos de dentro de `Application`
(POUs/GVLs/tasks) usam `type_guid`s distintos e consistentes por
categoria (`738bea1e-...` para pastas de POU, `6f9dac99-...` para POUs
folha, `ffbfa93a-...` para GVLs, `98a2708a-...`/`413e2a7d-...` para
tasks/seus POUs associados).

**Segurança**: nenhuma escrita, compilação, salvamento, acesso online ou
a documento textual em nenhum momento — confirmado tanto pela
`safety_declaration` quanto pela ausência de qualquer erro/exceção em
`errors.json` (vazio).

Com este resultado (árvore completa, 0 falhas relevantes, cruzamento
Application/active_application confirmado), a **fase de descoberta
estrutural está considerada encerrada**. `tree_walker.py` permanece
suspenso. Próximo desenvolvimento: leitura textual em lote controlado
(ver `docs/10-roadmap.md`, Entrega 2), sem voltar ao modelo de um probe
por objeto.

### Exportador textual (`ReadOnlyTextExporter`) criado — 2026-07-23

Extensão da mesma filosofia de navegação do scanner recursivo, agora
entrando pela **Application** (`project.active_application`, já confirmada
em runtime desde o probe 04 e cruzada com o caminho hierárquico via
`Device → Plc Logic` no scan de 117 nós acima) em vez da raiz do projeto, e
adicionando leitura de **conteúdo textual** (declaração/implementação ST)
por objeto.

Os membros usados são exatamente os já catalogados nesta mesma tabela de
evidência estática (ver seção "Objeto: projects" e a entrada "Ler
declaração/implementação textual" em
`docs/api/scriptengine-capabilities.md`): `IScriptObjectWithTextualDeclaration.textual_declaration`
e `IScriptObjectWithTextualImplementation.textual_implementation` (ambos
retornam `IScriptTextDocument`, com propriedade `.text`), confirmados por
reflection estática sobre `ScriptEngine3.dll` desde a fase de catálogo
estático. A novidade desta fase é o **uso concreto** desses membros: cada
um só é acessado depois que o indicador booleano correspondente
(`has_textual_declaration`/`has_textual_implementation`) vier **confirmado
e estritamente `True`** — portão obrigatório, nunca acesso especulativo.

Criado `common/read_only_text_exporter.py: ReadOnlyTextExporter` — DFS
iterativo (pilha explícita, idêntico ao padrão do scanner), com os mesmos
limites estruturais (`max_depth`/`max_total_nodes`/`max_children_per_node`)
mais três limites novos específicos de texto (`max_text_objects`,
`max_document_characters`, `max_total_characters`). Separação pura/impura:
`export()` nunca toca disco; `write_text_export_artifacts()` é uma camada
fina e separada que só serializa o que `export()` já decidiu gravar.
Preservação exata do texto lido — sem normalização/strip, SHA-256 por
documento, `character_length` (Python) vs. `byte_length` (UTF-8) reportados
separadamente.

38 testes permanentes em `tests/unit/test_read_only_text_exporter.py`
(suíte completa do repositório: 225 passed, 1 skipped).
`probes/13_validate_text_exporter.py` criado como wrapper fino (sonda a
identidade da Application e aborta ANTES de qualquer leitura textual se
divergir dos `expected_*` de `ExemploPlanta V1.0.project` — os mesmos valores
já confirmados acima: `name="Application"`,
`type_guid=639b491f-5557-464c-af91-1471bac9f549`,
`object_guid=00000000-0000-0000-0000-000000000001`). `config/text-export-defaults.yaml`
criado com os limites genéricos padrão.

Validado **externamente** (fora do MasterTool): dry-run sem `projects`
(degradação graciosa) e uma execução com árvore sintética via fakes (POU
com declaração+implementação multiline com acentos/CRLF/linha em branco,
GVL só com declaração, DUT só com declaração, pasta sem texto, texto vazio,
erros simulados nos indicadores de declaração e implementação) — texto e
SHA-256 conferidos byte-a-byte tanto em memória quanto no arquivo gravado
em disco. Ver especificação completa em `docs/12-read-only-text-export.md`.

### Exportação textual validada em runtime real — SUCESSO TOTAL — 2026-07-23

Execução real de `probes/13_validate_text_exporter.py` contra
`ExemploPlanta V1.0.project`, checksums verificados (`sha256sum -c` → 158/158
`OK`). Resultado:

```text
identidade da Application: name="Application" (bate), type_guid/object_guid
  batendo com os expected_* (00000000-0000-0000-0000-000000000001 /
  639b491f-5557-464c-af91-1471bac9f549) — application_identity_mismatch: []
total_nodes = 92
complete_nodes = 92 | partial_nodes = 0 | failed_nodes = 0
collection_errors = 0 | field_errors = 0 | index_errors = 0
duplicate_object_guids = 0
maximum_depth_reached = 3
declarations_saved = 68 | implementations_saved = 14
text_object_count = 68 | total_characters_saved = 66360
scan_complete = true
```

Nenhum limite atingido (`max_depth_reached`/`max_total_nodes_reached`/
`max_children_per_node_reached`/`max_text_objects_reached`/
`max_total_characters_reached`: todos `false`). `safety_declaration`
confirma `text_document_access=true` (intencional), todas as flags de
escrita/compilação/online `false`, `active_application_used=true`.

**Preservação exata confirmada por amostragem**: inspecionei
`objects/application_9_9__FB_VALVULA_EXEMPLO/declaration.st` (um Function
Block real do projeto) e recalculei o SHA-256 manualmente — bateu
exatamente com o registrado em `metadata.json`. Indentação mista
(tabs/espaços) do texto original preservada sem qualquer normalização.

**Achado pós-execução (correção sem nova execução no MasterTool)**: a
revisão do artefato real encontrado encontrou que `text-index.json` não
batia com o schema exigido (`build_text_index()` produzia um dict simples
em vez das 5 listas + 4 totais especificados). Corrigido via delta-fix,
depois **regenerado o `text-index.json` deste MESMO run** a partir da
`application-tree.json` já exportada (sem tocar o MasterTool de novo) —
os totais batem exatamente com as estatísticas originais do `report.json`
(`total_text_objects=68`, `total_characters=66360`,
`declarations=68`/`implementations=14`), confirmando consistência interna
dos dados reais. `checksums.sha256` também regenerado para refletir o
arquivo corrigido; 158/158 OK novamente.

**Fase de exportação textual considerada validada.** `tree_walker.py`
permanece suspenso.

---

## Modelo de introspecção — três estados (2026-07-23)

Após o achado do `dir()` vazio sobre `projects.primary` (ver seção de runtime
abaixo), a introspecção deste projeto passou a usar três estados, implementados
em `scripts/mastertool/common/capabilities.py`:

```text
confirmed      getattr(obj, nome) teve sucesso
unsupported    getattr falhou de forma compativel com "membro inexistente"
               (ate agora, so AttributeError foi tratado como tal)
unknown        dir() vazio, ou falha ambigua que nao prova ausencia
```

Regras:
- `dir()` nunca decide nada — é gravado só como `diagnostic_dir`
  (`authoritative: false`) para fins de log/depuração.
- A fonte de verdade é a whitelist explícita `capabilities.CAPABILITY_PROBES`
  (objeto → lista de nomes autorizados a testar), sondada nome a nome via
  `getattr` guardado.
- `02_dump_api_surface.py` foi reformulado (2026-07-23) para operar
  exclusivamente sobre essa whitelist — deixou de ser um "descobridor
  irrestrito" e passou a ser um **verificador de superfície conhecida**.
- `common/tree_walker.py` foi **suspenso**: as funções `get_children`/
  `describe_node`/`walk` agora levantam `TreeNavigationSuspended` sempre,
  porque os nomes que ele presumia (`get_children`, `children`, e os
  cogitados `find`/`get_objects`/`get_all_objects`) nunca foram confirmados.
  Reativação prevista via um `ProjectTreeAdapter` dedicado, só depois de
  evidência real (dumper oficial ou runtime). `03_list_project_tree.py` não
  foi alterado nem deve ser executado enquanto isso.
- Testes automatizados do comportamento de proxy dinâmico (dir vazio +
  getattr funcional) em `tests/unit/test_dynamic_proxy_capabilities.py`
  (camada externa, importando o módulo IronPython via `sys.path`).

---

## Runtime confirmado — 2026-07-23 (`00_smoke_test.py`)

Primeira execução real dentro do MasterTool IEC XE 3.63, projeto
`ExemploPlanta V1.0.project` aberto (device `NX3005`), via menu de scripting
(**Ferramentas**; caminho exato do submenu ainda não registrado — a
confirmar). Script executado com sucesso, 0 erro(s)/0 advertência(s)/0
mensagem(ns) próprias na aba "Mensagens de script". Relatório completo em
`workspace/logs/2026-07-23_10-28-07_00_smoke_test/report.json`.

Achados principais:

- `sys.platform == "cli"` confirmado → **IronPython confirmado** (não é só suposição).
- `sys.version` **não** retorna um número de versão de Python/IronPython — o
  host sobrescreve essa string com `"MT8500.exe MasterTool IEC XE,
  ScriptEngine.plugin 4.1.0.0"`. A versão `4.1.0.0` bate com a pasta
  `ScriptLib/4.1.0.0` (stdlib Python 2.7 embarcada) encontrada na análise
  estática — indício consistente, mas ainda não é a versão literal do Python.
  **Ação**: não usar `sys.version` como fonte de "versão do Python"; se
  precisarmos disso, investigar outro atributo (`sys.version_info`?) em uma
  próxima rodada.
- Global **`projects`**: presente, tipo .NET real **`ScriptProjects`** — nome
  diferente do driver `ScriptDriverProjects` visto na análise estática (como
  esperado: o driver registra um objeto-fachada distinto).
- Global **`system`**: presente, tipo .NET real **`SystemImpl`** — mesmo
  padrão (driver `ScriptDriverSystem` ≠ objeto exposto `SystemImpl`).
- **`projects.primary` existe e é truthy** — confirma a suposição usada em
  `common/project_access.py` (`hasattr(projects, "primary")`). Tipo .NET real:
  **`ExtendedObject[IScriptProject]`** — bate com a propriedade
  `PrimaryScriptProject : IExtendedObject<T>` vista na análise estática do
  driver (aqui T = `IScriptProject`, confirmado).
- `project.path` **funcionou** e retornou o caminho real do `.project` aberto.
- **`dir(project)` retornou lista VAZIA** (`members: []`) mesmo o objeto tendo
  `.path` acessível. Ver "Achado importante" abaixo — isto é um risco real
  para `02_dump_api_surface.py` e `tree_walker.py`, que dependem de `dir()`
  para enumerar membros.
- `project_access.get_object_name()` caiu no fallback `path` (não achou
  `get_name()`/`name` distintos) — por isso `name` e `path` saíram idênticos
  no relatório. Não é bug, é o comportamento documentado da função; só reforça
  que ainda não sabemos o nome "curto" do projeto via API.
- Nenhuma escrita, compilação ou acesso a `online`/`device_repository` foi
  solicitado (confirmado pelo próprio desenho do script — ver
  `safety_declaration` no relatório).

### Achado importante — `dir()` pode não enumerar objetos `ExtendedObject[T]`

O objeto `projects.primary` é do tipo `ExtendedObject[IScriptProject]` — um
wrapper genérico. `dir()` sobre ele voltou vazio, apesar de `.path` responder
normalmente via `hasattr`/`getattr` direto. Duas hipóteses:

1. `ExtendedObject[T]` implementa o protocolo dinâmico do DLR
   (`IDynamicMetaObjectProvider`) e expõe membros via `GetDynamicMemberNames()`
   em vez do mecanismo refletido que `dir()` normalmente usa — nesse caso
   `dir()` puro não é suficiente para introspecção nestes objetos.
2. `dir()` neste host só lista um subconjunto (ex.: membros "estáticos" do
   wrapper, não os membros dinâmicos da interface `IScriptProject`).

**Isto é um risco concreto para `02_dump_api_surface.py`**, cuja estratégia
principal é `dir(obj)` + `getattr` na classe. Antes de rodar esse script,
convém adicionar uma tentativa alternativa (ex.: checar se o objeto expõe
`GetDynamicMemberNames`/`__dict__`/algo equivalente em IronPython) — **ainda
não implementado**, aguardando decisão de continuar para `01_discover_environment.py`.

---

## Objeto: projects

### Disponível
**Confirmado em runtime** (2026-07-23, ver seção acima). Tipo real: `ScriptProjects`.

### Tipo observado
Runtime: `ScriptProjects` (objeto exposto ao script).
Estática: driver `_3S.CoDeSys.ScriptDriverProjects.ScriptDriverProjects`
(fábrica que registra o objeto `ScriptProjects` — não é o mesmo tipo).

### Propriedades (evidência estática — driver, podem não bater 1:1 com o global exposto)
- `PrimaryScriptProject` (tipo `IExtendedObject<T>`) — candidato a `.primary`
- `ArchiveCategories`

### Métodos (evidência estática)
- `CreateScriptObject(project, guid)`, `CreateScriptProject(int)`,
  `CreateScriptProject(IProject)`, `CreateScriptTextDocument(...)`,
  `CreateTextDocumentSource(...)`

### Tipos relacionados encontrados no mesmo plugin (evidência estática)
- **`ScriptApplication`** — provável tipo do objeto "aplicação" dentro do projeto:
  - Propriedades: `is_active_application`, `is_application`, `is_uptodate`,
    `is_online_change_possible`
  - Métodos: `build()`, `clean()`, `rebuild()`, `generate_code()`,
    `create_boot_application(output_filename[, update_compile_info, write_visu_files])`,
    `create_task_configuration()`
  - **Isto substitui a suposição antiga de `COMPILE_RELATED_MEMBERS =
    [build, rebuild, clean, compile, check_all_pool_objects, generate_code]`
    em `common/message_reader.py`** — os nomes reais parecem ser
    `build`/`rebuild`/`clean`/`generate_code` (sem `compile` nem
    `check_all_pool_objects`). Atualizado em `message_reader.py` em 2026-07-23.
- **`ScriptTextDocument`** — bate com a suposição de `object_reader.py`:
  - Propriedades: `text`, `length`, `linecount`
  - Métodos: `replace(...)`, `get_line(lineno)`, `get_text(...)`, `append(text)`,
    `insert(...)`, `remove(...)`
  - Confirma que `.textual_declaration.text` / `.textual_implementation.text`
    é um padrão plausível (falta confirmar o nome exato da propriedade holder).
- **`ScriptExternalFileObject`** — arquivos externos referenciados pelo projeto:
  `file_path`, `reference_mode`, `auto_update_mode`, `last_modification`,
  `length`, `calculate_checksum()`, `get_data(...)`.
- **`ScriptComparisonResult`** — comparação NATIVA entre dois projetos:
  `left_project`, `right_project`, `get_diff_state(obj)`,
  `get_changed_objects(state)`. **Relevante para `diff/project_diff.py`** —
  pode existir uma forma de comparar via API nativa em vez de só diff textual
  externo. Investigar no futuro (fase 2/3).

### Testes realizados
- 2026-07-23: runtime, `00_smoke_test.py` contra `ExemploPlanta V1.0.project`
  (MasterTool 3.63 real) — confirmou presença, tipo `ScriptProjects`, e
  `.primary` acessível e truthy (tipo `ExtendedObject[IScriptProject]`,
  `.path` legível, `dir()` vazio — ver achado importante acima).
- Evidência estática obtida em 2026-07-23 via `Assembly.ReflectionOnlyLoadFrom`
  (PowerShell) sobre `ScriptDriverProjects.plugin.dll` v4.1.0.0 (achados sobre
  o driver, não o objeto exposto).

### Riscos
Nenhum identificado para leitura. `ScriptApplication.build()/rebuild()/clean()`
são os candidatos reais de compilação — **não invocar** até a Fase 3 ser
liberada por decisão humana.

### Compatibilidade
MasterTool IEC XE 3.63 (plugin GUID `9fcfbd1c-b152-4bd8-8bc2-9773bb566084`, v4.1.0.0)

---

## Objeto: system

### Disponível
**Confirmado em runtime** (2026-07-23). Tipo real: `SystemImpl`.

### Tipo observado
Runtime: `SystemImpl` (objeto exposto ao script).
Estática: driver `_3S.CoDeSys.ScriptDriverSystem.ScriptDriverSystem` (fábrica
que registra o objeto `SystemImpl` — confirma o padrão driver≠objeto-exposto
já visto em `projects`/`ScriptProjects`).

### Tipos relacionados encontrados no mesmo plugin (evidência estática)
- **`ScriptMessage`** — objeto de mensagem de compilação/sistema:
  - Propriedades: `project`, `object`, `position`, `position_text`,
    `position_offset`, `length`, `text`, `severity` (enum `Severity`),
    `FontColor`, `has_details_handler`, `icon`, `number`, `prefix`
  - **Bate quase 1:1 com `compilation.schema.json`** (severity/text/object/location).
    Falta confirmar os valores do enum `Severity` (provável: Error/Warning/Info).
- **`ScriptCommand`** / **`ScriptCommands`** — comandos de sistema nomeados:
  `name`, `description`, `tokens`, `guid`, `execute(stBatchArguments)`;
  `ScriptCommands` é uma coleção iterável (`__len__`, `GetEnumerator`).
  Papel exato ainda não confirmado (pode ser comandos de menu do IDE).

### Testes realizados
- 2026-07-23: runtime, `00_smoke_test.py` — confirmou presença e tipo
  `SystemImpl` (apenas existência/tipo; nenhuma propriedade/método de
  `SystemImpl` foi lido ainda, por estar fora do escopo do smoke test).
- Evidência estática em 2026-07-23 via reflection sobre
  `ScriptDriverSystem.plugin.dll` v4.1.0.0 (achados sobre o driver e tipos
  relacionados `ScriptMessage`/`ScriptCommand`, não confirmados como membros
  de `SystemImpl` em si).

### Riscos
`ScriptCommand.execute(...)` tem potencial de efeito colateral — **nunca
invocar** sem confirmar exatamente o que cada comando faz.

### Compatibilidade
MasterTool IEC XE 3.63 (plugin GUID `d55b2d52-0f1c-4eda-a109-ec19a2544978`, v4.1.0.0)

---

## Objeto: scriptengine (motor em si) — STATUS: OPCIONAL, NÃO BLOQUEANTE

```text
status:   unavailable_from_confirmed_script_scope
required: false
blocking: false
```

### Disponível
Evidência estática: o tipo existe (`_3S.CoDeSys.ScriptEngine.ScriptEngine`,
assembly `ScriptEngine.plugin` v4.1.0.0). **Runtime (2026-07-23, 1ª execução
controlada):** o global `scriptengine` **NÃO foi encontrado** — nem no
escopo do script, nem via `import scriptengine`/builtins. Isso confirma
apenas que o nome testado não expõe o objeto a scripts; NÃO prova que o tipo
seja inacessível por outro caminho. Decisão: parar de perseguir por hipótese
(ver "Decisão de arquitetura" acima) — este objeto e `DumpScriptingApi` viram
**opcionais**, o projeto avança sem eles via o catálogo estático de navegação.

### Métodos relevantes (evidência estática — apenas para registro futuro)
- `Execute(string stScript)` — executar código adicional;
- `DumpScriptingApi(...)` — dumper oficial de API (assinatura completa
  documentada acima) — **não invocar mais por hipótese**;
- `CreatePythonDictionary()`, `CreatePythonList()`, `CreatePythonTuple(...)` —
  confirma binding real com tipos Python (dict/list/tuple) via IronPython/DLR;
- `DefaultSearchPath` (propriedade, `IList<T>`).

### Testes realizados
- 2026-07-23: runtime, 1ª execução controlada (`probes/02_dump_official_scripting_api.py`,
  `features.official_api_dump` habilitado temporariamente e revertido) —
  **global não encontrado, 0 chamadas realizadas, 0 risco**. Relatório:
  `workspace/logs/2026-07-23_10-54-06_02_dump_official_scripting_api/`.
- Evidência estática em 2026-07-23 via reflection sobre `ScriptEngine.plugin.dll` v4.1.0.0.

### Riscos
Nenhum incorrido (nenhuma chamada foi feita). `Execute(string)` roda código
arbitrário — não usar para nada além de introspecção controlada, **se** algum
dia um caminho de acesso for confirmado.

### Compatibilidade
MasterTool IEC XE 3.63 (plugin GUID `dc937c18-e9f0-434d-85b7-1b8f499e378a`, v4.1.0.0)

---

## Objeto: device_repository / árvore de dispositivos

### Disponível
_pendente_ — plugin `ScriptDriverDeviceObject.plugin.dll` existe e expõe tipos
de parâmetro/instância de device, mas não foi identificado o global raiz.

### Tipos relacionados (evidência estática)
- `ScriptDeviceInstance`: `FbName`, `FbNameDiag`, `BaseName`, `Instance`
  (`IScriptIoVariableMapping`), `InitMethodName`;
- `ScriptDeviceParameter` (e variantes Value/Enum/Range/Compound) — parâmetros
  de configuração de hardware. **Risco crítico** se algum dia usados para
  escrita (fora de escopo total nesta fase).

### Compatibilidade
MasterTool IEC XE 3.63 (plugin GUID `7a807e44-1a24-49f1-9799-154dd253ac8e`, v4.1.0.0)

---

## Objeto: online (NUNCA USAR)

### Disponível
Plugin `ScriptDriverOnline.plugin.dll` confirmado presente (tipos:
`ScriptGatewayDrivers`, `ScriptScanTargetDescription`, `ScriptDeviceUserList`
etc.) — ou seja, a capacidade de operação online EXISTE no produto.
**Confirma por que a proibição em `config/safety-policy.yaml` é necessária e
não apenas teórica.** Nenhum membro deste plugin deve ser chamado.

### Compatibilidade
MasterTool IEC XE 3.63 (plugin GUID `30979db2-a205-4067-80b1-c99b1c3dfbf3`, v4.1.0.0)

---

_Modelo para novos objetos: copie uma seção acima e preencha com dados reais,
citando a fonte exata (arquivo de export `workspace/exports/<ts>/...` para
evidência em runtime, ou caminho do plugin + método de extração para evidência
estática)._

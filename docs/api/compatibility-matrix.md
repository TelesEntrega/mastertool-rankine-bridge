# Matriz de compatibilidade

## Interpretadores

| Ambiente | Interpretador | Restrições |
|----------|---------------|------------|
| `scripts/mastertool/` | IronPython 2.7 (assumido — confirmar na Fase 0) | sem f-strings, pathlib, type hints, dataclasses, pip; usar `from __future__ import print_function`; strings via `%`/`.format` |
| `src/`, `tests/`, `tools/`, `scripts/maintenance/` | CPython 3.11+ | livre (dentro das dependências aprovadas) |

## Software

| Software | Versão alvo | Observações |
|----------|-------------|-------------|
| MasterTool IEC XE | 3.63 | única versão suportada nesta fase |
| Controlador | Altus NX3008 (ambiente real testado: NX3005) | referência; nenhum acesso online nesta fase |
| CODESYS base | ScriptEngine.plugin v4.1.0.0 | confirmado via `sys.version` (banner do host) e reflection estática |

## Assemblies-núcleo de scripting (2026-07-23, reflection estática)

| Assembly | Papel |
|----------|-------|
| `ScriptEngine.plugin` v4.1.0.0 | motor de scripting (`ScriptEngine`, `ExtendedObject<T>`) |
| `ScriptEngine3` v4.1.0.0 | **assembly-núcleo compartilhado** com as interfaces reais: `IScriptProject`, `IScriptTreeObject`, `IScriptObject`, `IScriptTextDocument`, `IScriptObjectWithTextualDeclaration`/`...Implementation`, `IScriptPouObjectCollection`, `PouType` |
| `ScriptDriverProjects.plugin` v4.1.0.0 | driver que registra `projects` (tipo real exposto: `ScriptProjects`); também define `ScriptApplication`, `ScriptTextDocument`, `ScriptComparisonResult` |
| `ScriptDriverSystem.plugin` v4.1.0.0 | driver que registra `system` (tipo real exposto: `SystemImpl`); define `ScriptMessage`, `ScriptCommand` |
| `ScriptDriverOnline.plugin` v4.1.0.0 | operações online — **nunca usar** |
| `ScriptDriverDeviceObject.plugin` v4.1.0.0 | árvore de dispositivos/parâmetros de hardware |

Padrão observado: cada plugin `ScriptDriverX` é um *driver/fábrica*
(`OnDriverLoad`) que registra um objeto-fachada com nome DIFERENTE do driver
(`ScriptDriverProjects` → expõe `ScriptProjects`; `ScriptDriverSystem` →
expõe `SystemImpl`). Não presumir que o nome do plugin é o nome do tipo
exposto ao script.

## Diferenças IronPython 2.7 relevantes

- `print` é função apenas com `from __future__ import print_function`;
- `unicode`/`long` existem (tratados em `common/serialization.py`);
- `os.makedirs` sem `exist_ok` → usar `common/file_io.ensure_dir`;
- I/O de texto com `codecs.open(..., "utf-8")`;
- objetos .NET "normais": `dir()` funciona, mas propriedades de instância
  podem ter efeitos colaterais — introspecção via classe
  (ver `02_dump_api_surface.py`);
- **objetos `ExtendedObject<T>` (ex.: `projects.primary`) são proxies
  dinâmicos** (`System.Dynamic.IDynamicMetaObjectProvider`) — `dir()` retorna
  vazio mesmo quando `getattr` funciona normalmente (membro real fica em
  campo privado `BASE_OBJECT`, encaminhado via `GetMetaObject()`). **Nunca
  usar `dir()` para decidir se um membro existe** nesses objetos — usar
  sondagem explícita (`common/capabilities.py`). Confirmado por reflection
  estática em 2026-07-23 (ver `docs/api/mastertool-api-observations.md`).

## Navegação recursiva genérica (2026-07-23)

Confirmado em runtime real (probes 05-10, ver
`docs/api/mastertool-api-observations.md`) que a cadeia
`get_children(False)` → `Count` → indexador nativo →
`is_folder`/`type`/`guid`/`get_name(False)` funciona **identicamente** em
qualquer nível da árvore (raiz `IScriptProject` e nós filhos
`IScriptObject`), sempre retornando o mesmo tipo concreto
(`System.Collections.Generic.List<IExtendedObject<IScriptObject>>`) e as
mesmas interfaces confirmadas (`ICollection`/`IList`/`IReadOnlyList`/
`IReadOnlyCollection`, genéricas e não-genéricas). Generalizado em
`common/read_only_project_scanner.py: ReadOnlyProjectScanner` — ver
`docs/11-read-only-project-scanner.md`.

## Leitura textual (2026-07-23)

`common/read_only_text_exporter.py: ReadOnlyTextExporter` estende a mesma
navegação para a subárvore da Application, usando
`has_textual_declaration`/`textual_declaration.text`/
`has_textual_implementation`/`textual_implementation.text` como portões
booleanos obrigatórios (nunca acesso especulativo). Validado em runtime
real (2026-07-23, `ExemploPlanta V1.0.project`, 92 nós, 68 objetos com texto,
0 erros, checksums 158/158 OK) além de 38 testes unitários — ver
`docs/12-read-only-text-export.md`.

## Incompatibilidades encontradas no ambiente real

- `sys.version` não retorna a versão do Python/IronPython — o MasterTool
  sobrescreve com um banner do produto (`"MT8500.exe MasterTool IEC XE,
  ScriptEngine.plugin 4.1.0.0"`). `sys.platform == "cli"` continua confiável
  para detectar IronPython. Confirmado em 2026-07-23 via `00_smoke_test.py`.
- `dir()` retorna lista vazia sobre objetos `ExtendedObject<T>` (ver acima) —
  confirmado em runtime (2026-07-23) e explicado por reflection estática
  (2026-07-23, mesmo dia).

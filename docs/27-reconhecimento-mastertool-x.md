# W0 — Reconhecimento do MasterTool X

Registro de campo do marco **W0** da trilha `MasterTool X controlled project
authoring`. Mede o que existe na máquina antes de qualquer escrita.

**Nenhum método mutável foi invocado. Nenhum processo do MasterTool foi
lançado.** Tudo aqui é metadado de arquivo e reflexão somente-metadados
(`Assembly.ReflectionOnlyLoadFrom`), que lê o assembly sem executar uma linha
dele.

## Numeração dos documentos

O contrato de escrita controlada foi planejado como `docs/27`. Ele passa a ser
`docs/28`, e este documento fica com o 27: a evidência de W0 é volumosa o
bastante para ter documento próprio, e um contrato normativo não deve carregar
o registro de campo que o justifica. Além disso o contrato **ainda não pode ser
fechado** — falta a metade de runtime de W0, que exige o usuário (ver §O que
W0 ainda não mediu).

## 1. Identidade do produto instalado

Medido pelos metadados do executável, sem lançá-lo:

| | |
|---|---|
| Atalho | `Mastertool X 4.1.0.lnk` — **o caminho do atalho muda; resolver sempre** |
| Alvo | `C:\Program Files\Altus\MT9000 4.1.0\MT9000\Common\MT9000.exe` |
| Executável | **`MT9000.exe`** — não é mais `MT8500.exe` |
| `FileVersion` | `4.1.0.11` |
| `ProductVersion` | `4.1.0.11` |
| `ProductName` / `CompanyName` | `Mastertool` / `Altus Sistemas de Automação S.A.` |
| Identidade do assembly | `MT9000, Version=4.1.0.11, Culture=neutral, PublicKeyToken=null` |
| `ProcessorArchitecture` | `MSIL` (AnyCPU) |
| Local de instalação | `Program Files` — **não** `Program Files (x86)` |

**A designação "X4.1" está confirmada pelo executável**: o produto se declara
`4.1.0.11`, e não `4.0.0`. A dúvida de origem (fontes públicas citam
MasterTool X 4.0.0) fica resolvida por medição na máquina, não por documento.

### Sobre "64 bits"

O cabeçalho PE traz `machine=0x014C` (I386) e `ProcessorArchitecture=MSIL` —
assinatura de assembly **AnyCPU**, que roda como processo de 64 bits num
Windows de 64 bits. Portanto:

- a instalação em `Program Files` (não `(x86)`) e o diretório irmão `Common32`
  são evidência forte de produto de 64 bits;
- mas **o bitness do processo em execução não foi medido** — só uma execução
  real mostra isso, e ela pertence à metade de runtime de W0.

Registrar "64 bits" como fato agora seria afirmar mais do que foi medido.

### Instalações presentes nesta máquina

```text
64 bits   MT8500 3.70, 3.71, 3.75, MT9000 4.0.0, MT9000 4.1.0
32 bits   MT8500 3.50, 3.51, 3.52, 3.61, 3.62, 3.63, 3.70, 3.71, 3.75
```

Há **duas** instalações de MasterTool X (4.0.0 e 4.1.0). O atalho aponta para a
4.1.0. Como o repositório de dispositivos é por versão (`docs/26`), 4.0.0 e
4.1.0 têm repositórios independentes.

## 2. Runtime de script

| | MT9000 4.1.0 | MT8500 3.70 |
|---|---|---|
| `IronPython.dll` | **2.7.12.0** | **2.7.12.0** |
| `IronPython.Modules.dll` | 2.7.12.0 | 2.7.12.0 |
| Diretório de stdlib | `ScriptLib\4.1.0.0\` (563 arquivos) + `Stubs\` | `ScriptLib\4.1.0.0\` + `Stubs\` |

A stdlib é claramente Python 2 (`Bastion.py`, `anydbm.py`, `clrtype.py`,
`BaseHTTPServer.py`). **O runtime de script não mudou de geração**: continua
IronPython 2.7.12, e o código dos probes continua tendo de ser Python 2.7
válido.

`sys.version` — o banner que em 3.70 passou a carregar o número da versão
(`docs/26`) — **não foi medido aqui**: só existe dentro do processo.

## 3. Assemblies de scripting

| Assembly | MT9000 4.1.0 | MT8500 3.70 |
|---|---|---|
| `ScriptEngine3` | **4.2.0.0** | 4.1.0.0 |
| `ScriptEngine.plugin` | **4.2.0.0** | 4.1.0.0 |
| `ScriptDriverProjects.plugin` | **4.2.0.0** | 4.1.0.0 |
| `ScriptDriverSystem.plugin` | **4.2.0.0** | 4.1.0.0 |
| `ScriptDriverDeviceObject.plugin` | 4.2.0.0 | 4.1.0.0 |
| `ImageRuntimeVersion` de `ScriptEngine3` | `v2.0.50727` | `v2.0.50727` |

**A versão dos assemblies subiu de 4.1.0.0 para 4.2.0.0.** A conclusão de
`docs/26` — "a API de scripting não mudou" — valia para 3.63 × 3.70 e **não se
estende ao MasterTool X**. Aqui houve mudança de versão, e a pergunta passa a
ser o que mudou dentro dela.

Diferença de nomenclatura que quebra suposição de caminho: em `Common\` os
arquivos se chamam `ScriptEngine.dll`, `ScriptEngine2.dll` e
`ScriptEngine3.dll` (sem `.plugin`), enquanto os drivers ficam em
`PlugIns\<Nome>\<Versão>\<Nome>.plugin.dll`.

## 4. Método da comparação

Duas medições independentes, ambas somente-metadados:

1. **Catálogo por sementes** — `tools/static-api-catalog.ps1`, o instrumento já
   versionado, rodado contra as duas instalações. Cobre os 15 tipos que o
   projeto já usa, mais o grafo de profundidade 1.
2. **Varredura ampla** — todos os tipos públicos de `ScriptEngine3`,
   `ScriptEngine.plugin`, `ScriptDriverProjects.plugin` e
   `ScriptDriverSystem.plugin`, nas duas instalações. Necessária porque as APIs
   de criação não são alcançáveis a partir das sementes atuais.

Ambas exigem um `ReflectionOnlyAssemblyResolve` que resolva dependências pelo
diretório de instalação; sem ele, `GetMembers` levanta `FileLoadException` na
primeira dependência não pré-carregada (`ProjectArchive`).

### A normalização que evita um diff falso

O nome de um tipo genérico carrega a identidade do assembly:

```text
IExtendedObject`1[[IScriptProject, ScriptEngine3, Version=4.2.0.0, ...]]
IExtendedObject`1[[IScriptProject, ScriptEngine3, Version=4.1.0.0, ...]]
```

Sem neutralizar `Version=`, **todo** membro de tipo genérico aparece como
diferente. Na primeira passagem isso produziu 27 diferenças falsas; com a
normalização sobraram **1**. Comparar só por nome de membro seria o erro
oposto — esconderia mudança de parâmetro ou de retorno. A chave usada é
`(tipo declarante, categoria, nome, assinatura normalizada)`, com assinatura
montada de retorno + tipos e nomes de parâmetro + opcionalidade.

### Instrumento ainda não versionado

O catálogo por sementes usa ferramenta versionada. A **varredura ampla ainda
não está em `tools/`**: ela emite um schema diferente do que
`src/mastertool_bridge/static_api/` consome, e versioná-la exige alinhar os
dois schemas ou duplicar a análise. Fica como pendência declarada — os números
abaixo são reproduzíveis pelo método descrito, mas ainda não por um comando
único do repositório.

## 5. Resultado — superfície das sementes

Sobre os 15 tipos que o projeto já usa:

```text
tipos catalogados      15  x  15     nenhum a mais, nenhum a menos
membros comparados    141  x  140
so no MT9000            1
so no 3.70              0
```

A única diferença é uma **sobrecarga acrescentada**:

```text
IScriptProjects6.open_archive(..., categories_to_extract?)
```

**Nada do que o projeto usa hoje foi removido ou teve assinatura alterada.**

## 6. Resultado — superfície ampla

```text
tipos publicos     304 (MT9000)  x  312 (3.70)
  so no MT9000      18
  so no 3.70        26   dos quais 21 sao DocuDumper
membros          1.544 (MT9000)  x 1.616 (3.70)
  so no MT9000      54
  so no 3.70       126   dos quais 112 sao DocuDumper
```

### O que foi removido de fato

Fora do `DocuDumper` (infraestrutura de dump de documentação), só 14 membros
sumiram:

| Tipo | Membros | Consequência |
|---|---|---|
| `IUndocumentedSystemMembers` | `dump_scripting_api` (2 sobrecargas) | **relevante**: era a rota de dump da API de dentro do produto. No MasterTool X ela não existe — reflexão estática passa a ser o único caminho |
| `ISystemForPatches` | `background_loading_of_libraries_finished` | irrelevante para esta trilha |
| `UI.PasswordDialog`, `UI.UsernamePasswordDialog` | `Cancellable`, `Message` | diálogos de senha deixaram de ser expostos ao script |
| `ScriptDebuggingMode` | 7 membros | modo de depuração de script deixou de ser comando exposto |

**Nenhuma API de navegação, leitura, export ou criação foi removida.**

### O que foi acrescentado

| Tipo novo | Membros | Por que importa |
|---|---|---|
| `IScriptIecLanguageObjectContainer4` | `create_program`, `create_function`, `create_function_block` | **criação de POU tipada**, exatamente o alvo de W1 |
| `IScriptProjectSettings2` | `get_compilerversion`, `set_compilerversion_to_newest`, `project_defines` | um getter e **dois mutadores** de configuração de projeto |
| `ISystem6` | `script_prompt_handling`, `process_script_prompts`, `log_prompt_details` | controle de diálogo por script — ver §Riscos |
| `ScriptPromptHandling` (enum) | `SuppressPrompts`, `ForwardUnknownPrompts`, `AlwaysForwardPrompts`, `LogPrompts` | idem |
| `ScriptingException`, `ScriptingErrorCode` e duas subclasses | erro tipado com código | erro de script deixa de ser só texto: dá para classificar |
| `IScriptObject7`, `IScriptProject13` | `find_ignore_transient_objects`, `finish_load_project` | busca que ignora objeto transiente |
| `IScriptTransientObjectMarker` e marcadores | `is_transient_object` | **objeto transiente é conceito novo** e precisa entrar em qualquer diff estrutural |
| `IScriptLibManObject3` | `download_missing_libraries` | **proibido** por contrato: faz rede |
| `IScriptExecutor5` | `ResetMainScope` | escopo do interpretador |
| `ScriptMessage` (driver) | `Text`, `Severity`, `Position`, `ObjectGuid`, ... | mensagem de compilação com posição e objeto — útil em W2 |

## 7. Catálogo das APIs candidatas de escrita

Todas medidas no MT9000 4.1.0. `=` significa **assinatura idêntica à do
3.70**; `NOVO`, que não existe no 3.70.

### Criação de objeto IEC

| Estado | Tipo declarante | Membro |
|---|---|---|
| `=` | `IScriptIecLanguageObjectContainer` | `create_pou(name, PouType type?, Guid? language?, string return_type?, string base_type?, string interfaces?)` |
| `=` | `IScriptIecLanguageObjectContainer` | `create_gvl(name)` |
| `=` | `IScriptIecLanguageObjectContainer` | `create_dut(name, DutType type?, string baseType?)` |
| `=` | `IScriptIecLanguageObjectContainer` | `create_interface(name, string baseInterfaces?)` |
| `=` | `IScriptIecLanguageObjectContainer2` | `create_pou(SpecialPouType type)` |
| `=` | `IScriptIecLanguageObjectContainer3` | `create_persistentvars(name)` |
| `NOVO` | `IScriptIecLanguageObjectContainer4` | `create_program(name, Guid? language?)` |
| `NOVO` | `IScriptIecLanguageObjectContainer4` | `create_function(name, string return_type, Guid? language?)` |
| `NOVO` | `IScriptIecLanguageObjectContainer4` | `create_function_block(name, Guid? language?, string base_type?, string interfaces?)` |
| `=` | `IScriptObject3` | `create_folder(foldername)` |
| `=` | `IScriptProject6` | `create_folder(foldername)` e `create_folder(foldername, Guid structured_view)` |
| `=` | `IScriptTaskConfigObject` | `create_task(...)` |
| `=` | `IScriptApplication3` | `create_task_configuration(...)` |

Todos devolvem `IExtendedObject<IScriptObject>` — o mesmo envelope que o resto
do projeto já manipula.

**A rota A (API nativa) existe e é tipada.** As três funções de W1 — GVL vazia,
POU `PROGRAM`, depois `FUNCTION_BLOCK` e `FUNCTION` — têm método próprio, e o
caminho antigo (`create_pou` com `PouType`) continua disponível como
alternativa comprovada no 3.70.

### Seleção de linguagem

`IScriptImplementationLanguages` expõe um `Guid` por linguagem, todos `=`:

```text
st   ladder   fbd   sfc   cfc   instruction_list   page_oriented_cfc   uml_statechart
```

É esse GUID que entra no parâmetro `language?` dos `create_*`. **A linguagem
não é string** — não há espaço para grafia livre.

### Conteúdo textual

| Estado | Tipo | Membro |
|---|---|---|
| `=` | `IScriptObjectWithTextualDeclaration` | `textual_declaration` → `IScriptTextDocument` (get=True, **set=False**) |
| `=` | `IScriptObjectWithTextualImplementation` | `textual_implementation` → `IScriptTextDocument` (get=True, **set=False**) |
| `=` | `IScriptTextualObjectMarker` | `has_textual_declaration`, `has_textual_implementation` |

A propriedade **não tem setter**: escreve-se pelo documento devolvido, cuja
superfície é `append`, `insert` (por offset ou linha/coluna), `replace`,
`replace_line`, `remove`, mais os getters `text`, `length`, `linecount`,
`get_line`, `get_text`. Todos `=`.

`replace(new_text)` substitui o documento inteiro — é a operação mais simples
para W2 e a mais fácil de verificar, porque o estado final não depende de
offset nenhum.

### Persistência e verificação

| Estado | Tipo | Membro |
|---|---|---|
| `=` | `IScriptProject` | `save()`, `save_as(path, password?)`, `save_archive(path)`, `close()` |
| `=` | `IScriptProject` | `dirty` (get) — diz se há alteração não salva |
| `=` | `IScriptApplication` | `build()`, `rebuild()`, `clean()`, `create_boot_application()` |
| `NOVO` | `IScriptProjectSettings2` | `get_compilerversion()`, `set_compilerversion_to_newest()`, `project_defines` |

`save_as` existe com a assinatura esperada — o **save-as obrigatório** do
contrato é executável.

### Importação (rota B)

| Estado | Tipo | Membro |
|---|---|---|
| `=` | `IScriptObject` / `IScriptObject2` | `import_xml(IImportReporter reporter, string dataOrPath)` |
| `=` | `IScriptObject5` | `import_xml(dataOrPath, bool import_folder_structure?)` e `import_xml(ConflictResolve, ...)` |
| `=` | `IScriptProject` / `2` / `9` | as mesmas formas no nível do projeto |
| `=` | `IScriptObject2` / `IScriptProject2` | `import_native(...)` |

**A rota B existe e aceita resolução de conflito explícita**
(`_3S.CoDeSys.PLCopenXML.ConflictResolve`) — o que a torna candidata séria para
W5 (Ladder), onde montar o grafo pela API seria muito mais arriscado.

Nota de escopo: até hoje `import_xml` era **permanentemente fora de escopo**
(`docs/23`). Ela deixa de ser proibida por princípio e passa a ser
**não-autorizada até que o contrato de W3 a governe** — a diferença importa,
porque a trilha de escrita é exatamente o que muda essa condição.

### Renome e remoção

`IScriptObject.rename(stNewName)` e `IScriptObject.remove()`, ambos `=`.
`IScriptPouObjectCollection.remove(index|pou_name)`, `=`.

## 8. Riscos registrados

1. **`ISystem6.script_prompt_handling` pode suprimir diálogo.**
   `SuppressPrompts` faz o produto deixar de perguntar — e a regra do projeto é
   "diálogo inesperado → cancelar e registrar". Suprimir prompt converteria uma
   parada segura em decisão silenciosa. O contrato deve **proibir
   `SuppressPrompts`** e considerar `LogPrompts` como o único valor
   aceitável para auditoria.
2. **`IScriptLibManObject3.download_missing_libraries` faz rede.** Colide com
   "nenhum download". Vai para a lista proibida.
3. **`set_compilerversion_to_newest()` altera o projeto sem parecer.** Muda a
   versão de compilador do projeto — mutação de alto impacto disfarçada de
   configuração. Proibida fora de plano explícito.
4. **Objeto transiente é conceito novo.** `is_transient_object` e
   `find_ignore_transient_objects` não existiam no 3.70. Um diff estrutural que
   ignore isso pode acusar objeto criado/removido que é só transiente. Precisa
   ser tratado antes de W3.
5. **`create_*` devolve objeto já inserido na árvore.** Não há passo de
   "confirmar": o retorno é o objeto criado. Logo a unidade de rollback é o
   **projeto**, não a operação — daí a cópia de trabalho ser obrigatória desde
   W1, e não só em W3.
6. **`dump_scripting_api` não existe mais.** Não dá para conferir a superfície
   de dentro do produto; a reflexão estática vira a única fonte, e um erro nela
   não tem segunda opinião.
7. **Duas versões de MasterTool X instaladas.** 4.0.0 e 4.1.0 com repositórios
   de dispositivo independentes. Todo artefato deve registrar **qual** produziu.
8. **O nome do executável mudou.** Toda invocação documentada em `docs/15`,
   `docs/22` e `docs/23` usa `MT8500.exe`. Nenhuma delas vale como está.

## 9. A metade de runtime — MEDIDA em 2026-07-31

Sessão supervisionada, seis execuções, UI visível, offline, sobre cópia
descartável em diretório isolado. **Nenhum diálogo apareceu em nenhuma delas.**

| Etapa | Comando | Duração | Exit | Órfãos | Cópia |
|---|---|---|---|---|---|
| v1 | `--runscript=` | 139,0 s | 0 | 0 | inalterada |
| v2 | + `--scriptargs:` | 32,8 s | 0 | 0 | inalterada |
| v3 | + `--project=` | 34,8 s | 0 | 0 | inalterada |
| identity | probe 26 | 52,7 s | 0 | 0 | inalterada |
| scan | probe 21 | 373,3 s | 0 | 0 | inalterada |
| scan (confirmação) | probe 21, limites distintivos | 373,3 s | 0 | 0 | inalterada |

As durações medem a janela aberta, não o script: o MasterTool X **não fecha
sozinho** depois do `--runscript` (esperado, sem `--noUI`), então o tempo é o
que o operador levou para fechar. O script em si roda em ~1 s: na v1 a janela
subiu às 10:08:40 e o artefato foi escrito às 10:08:41.

### A linha de comando sobreviveu inteira

```text
MT9000.exe --project="<copia>" --runscript="<probe>" --scriptargs:"--output=<dir> --max-depth=7 --max-total-nodes=1234"
```

As três opções funcionam, **na mesma forma do MT8500 3.63**: `--runscript=`,
`--scriptargs:` e `--project=`. Não foi preciso testar as variantes com
separador por espaço.

O `--scriptargs` **continua quebrando o valor em espaço em branco**, agora
medido no MasterTool X: os três argumentos chegaram como elementos separados
de `argv`. Isso é bom para passar vários argumentos e fatal para um único
valor que contenha espaço — a regra "nenhum caminho com espaço" segue valendo,
agora por medição e não por herança.

### O identificador do runtime

```text
sys.version    MT9000.exe Mastertool X 4.1.0.11, ScriptEngine.plugin 4.2.0.0
sys.platform   cli
version_info   2.7.12.final.0
sys.executable MT9000.exe
```

O banner agora carrega **produto e ScriptEngine numa string só** — em 3.63 não
carregava versão nenhuma, em 3.70 carregava só a do produto. Ainda assim o
probe 26 tira a versão do ScriptEngine do **assembly carregado**, não do
banner: o formato mudou três vezes em três versões e não há por que apostar na
quarta.

### Bitness, medido

```text
IntPtr.Size                 8
Environment.Is64BitProcess  True
bitness_evidence            System.IntPtr.Size
modulo real do processo     C:\Program Files\Altus\MT9000 4.1.0\MT9000\Common\MT9000.exe
```

**64 bits confirmado por medição**, e o módulo real prova que a execução foi na
instalação **4.1.0**, não na 4.0.0 que também está na máquina.

### Assemblies carregados

792 no AppDomain, 36 de interesse. Todos batem com a reflexão estática:

```text
ScriptEngine3                 4.2.0.0     ScriptEngine.plugin           4.2.0.0
ScriptDriverProjects.plugin   4.2.0.0     ScriptDriverSystem.plugin     4.2.0.0
ScriptDriverDeviceObject      4.2.0.0     IronPython / .Modules         2.7.12.0
MT9000                        4.1.0.11    Microsoft.Scripting           1.3.1.0
ProjectArchive                3.5.18.60   VersionCompatibilityManager   3.5.18.60
```

O núcleo CODESYS por baixo carrega em **3.5.18.60** — o que explica por que a
superfície de scripting é aditiva em vez de reescrita.

### Os probes aprovados rodaram sem alteração

`probes/15` e `probes/21`, escritos para o MT8500 3.63, rodaram no MasterTool X
**sem uma linha alterada**. O scan da cópia descartável:

```text
status complete   3 raizes   34 nos   profundidade 6   0 erros   nenhum limite atingido
sha256 do projeto identico antes e depois
```

E a declaração de segurança do probe 21 no artefato real:
`object_creation`, `object_modification`, `project_save`, `project_write`,
`project_close`, `device_repository_access`, `device_configuration_access`,
`online_access`, `download`, `force`, `text_document_access` — **todos
`false`**.

### O defeito de método que a sessão expôs

A primeira execução do scan passou `--max-depth=32 --max-total-nodes=20000` e o
manifesto registrou exatamente 32 e 20000 — que são **os defaults do próprio
probe**. Os dois valores coincidirem tornou a evidência inútil: não dava para
distinguir "o argumento chegou" de "o argumento foi descartado e o default
valeu", e as duas hipóteses têm causas opostas.

A correção foi gravar o `argv` cru no manifesto (`schema_version` 1.1) e
repetir com valores impossíveis de confundir. Aí as três evidências
apareceram juntas — `argv` com `--max-depth=7` e `--max-total-nodes=1234`,
`manifest.max_depth = 7`, `manifest.max_total_nodes = 1234` — e o resultado
observado não mudou (3 raízes, 34 nós, profundidade 6), como tinha de ser para
uma árvore que cabe folgada nos dois limites.

**Um valor de teste igual ao default não é evidência.** Vale para qualquer
verificação futura desta trilha.

### Efeito lateral do IDE: os arquivos `.opt`

Abrir a cópia cria dois arquivos irmãos, no mesmo diretório do `.project`:

```text
<nome>-AllUsers.opt
<nome>-<usuario>-<maquina>.opt
```

São opções de IDE (layout de janelas, estado de sessão), **não** conteúdo de
projeto: o `.project` em si terminou com o mesmo SHA-256 nas seis execuções.
Aparecem já na primeira abertura e não crescem depois.

É por isso que a cópia descartável mora em **diretório próprio**, e não ao lado
do arquivo de origem. O arquivo indicado para a sessão convivia na mesma pasta
com o projeto de produção — e é byte a byte idêntico a ele. Tivesse a sessão
rodado ali, esses dois `.opt` teriam sido escritos na pasta do projeto real. O
isolamento não é cerimônia: é a diferença entre efeito lateral contido e
efeito lateral no diretório de produção.

Consequência para o contrato: o diff estrutural de W3 deve comparar o
`.project`, **nunca a pasta**, ou todo ciclo acusará mudança que é só o IDE
gravando preferência de janela.

### Sobra de teste contamina a busca por artefato

Achado do host, não do MasterTool: a suíte de testes importa `probes/15`, cujo
rodapé chama `main()`, e isso grava um artefato de verdade em
`<repo>\workspace\logs`. Um `pytest` rodado depois da sessão produziria o
artefato **mais novo** e ele seria colhido como se fosse o da execução real.

A distinção está no runtime: execução real traz `platform` `cli`; sobra de
teste traz `win32`. Qualquer coletor de artefato desta trilha precisa filtrar
por isso, e não só por data.

### O que continua sem medição

| Pendente | Situação |
|---|---|
| `--noUI` | **não testado de propósito**: a sessão exige UI visível |
| Diretório efetivo do Device Repository | não lido — `device_repository` inicia comunicação ao ter propriedades lidas (`docs/24`); fica com o host, do disco |
| Export mínimo no MasterTool X | não executado: a cópia é um projeto vazio, sem POU gráfica para exportar |
| Propagação do exit code do script | os seis `exit 0` são do processo depois do fechamento manual, não do script. Continua sem evidência — e o `status` do manifesto segue sendo a fonte autoritativa |

### As opções de script sobrevivem — por nome

O `MT9000.exe` é um lançador pequeno (647 KB) e **não contém** as strings
`runscript`, `scriptargs` nem `--project`. Elas são declaradas pelo plugin: em
`ScriptEngine.plugin.dll` **4.2.0.0** estão presentes

```text
runscript   scriptargs   enablescripttracing
```

junto de `ScriptEngineScriptArgs_Description` — e a varredura de tipos confirma
que `ScriptEngineRunScript` continua existindo (só `ScriptDebuggingMode` foi
removido).

Isso reduz muito o risco do primeiro ensaio supervisionado: a família de opções
sobreviveu à mudança de geração. **O que ainda não está provado é a sintaxe**
(`--runscript=<caminho>` versus `--runscript <caminho>`, e se `--scriptargs:`
continua quebrando o valor em espaço em branco, achado do probe 15). String
presente em binário prova que o nome existe, não como ele é passado.

Presença de string é evidência de nome, não de contrato de invocação — e a
diferença é exatamente o tipo de coisa que este projeto não presume.

### Instrumentos preparados para a metade de runtime

| Instrumento | Papel | Estado |
|---|---|---|
| `probes/15_validate_command_line_execution.py` | Etapa 1 — prova a sintaxe da linha de comando. **Reusado sem alteração**, de propósito: se ele já rodou em 3.63 e 3.70, uma falha aqui isola a variável "sintaxe" da variável "probe" | versionado, inalterado |
| `probes/26_probe_runtime_identity.py` | Etapa 2 — mede o que só existe dentro do processo: bitness por `IntPtr.Size`, assemblies **carregados** no AppDomain, módulo real do processo, `sys.version` cru | **novo** |
| `probes/21_scan_project_tree_full.py` | Etapa 3 — varredura recursiva read-only | versionado, inalterado |

O probe 26 determina a versão do ScriptEngine pelo **assembly carregado**, não
pelo parse do banner de `sys.version`. O banner mudou de formato entre 3.63 e
3.70 e supor que o do MasterTool X siga o mesmo padrão seria a inferência que
este projeto não faz. A lógica pura mora em `common/probe_cli.py`
(`assembly_name_matches`, `scriptengine_version_from_assemblies`), com testes —
probe que roda dentro do MasterTool não é testável; módulo comum é.

O probe 26 **não toca `device_repository`**: ele está marcado em
`common/compatibility.py` como capaz de iniciar comunicação ao ter
propriedades lidas. O diretório do Device Repository é lido do disco pelo
host, fora do processo.

## 10. Esqueleto do contrato (`docs/28`)

Cláusulas que a evidência de W0 já sustenta, para o documento normativo:

```text
projeto descartavel obrigatorio        nenhuma sessao online
nenhum download                        nenhum force
backup e hashes antes e depois         plano de alteracao declarado
allowlist LITERAL de operacoes         proibicao de API nao catalogada
save_as obrigatorio                    reabertura e verificacao
compilacao offline                     diff estrutural
rollback                               criterios de aborto
trilha de auditoria
```

Acrescentadas por achado de W0, e que não estavam previstas:

```text
proibir ScriptPromptHandling.SuppressPrompts
proibir download_missing_libraries
proibir set_compilerversion_to_newest
tratar objeto transiente no diff estrutural
registrar SEMPRE qual instalacao (4.0.0 ou 4.1.0) produziu o artefato
linguagem por GUID de IScriptImplementationLanguages, nunca por string
```

## 11. Conclusão de W0

- A designação **X4.1 está confirmada**: `MT9000.exe` `4.1.0.11`.
- O runtime de script **não mudou**: IronPython 2.7.12, igual ao 3.70.
- A API de scripting **mudou de versão** (4.1.0.0 → 4.2.0.0), mas a mudança é
  **aditiva** onde interessa: nada que o projeto usa foi removido ou teve
  assinatura alterada, e a única diferença nas sementes é uma sobrecarga a
  mais.
- **A rota A é viável e tipada.** Todas as APIs necessárias para W1 e W2
  existem: `create_gvl`, `create_pou`/`create_program`/`create_function_block`,
  `create_folder`, `textual_declaration`/`textual_implementation` via
  `IScriptTextDocument`, `save_as`, `build`.
- **A rota B também existe**, com resolução de conflito explícita.
- A metade de runtime **confirmou** a estática em todos os pontos verificáveis:
  ScriptEngine3 4.2.0.0 carregado, IronPython 2.7.12, MT9000 4.1.0.11, 36
  assemblies de scripting coerentes com o disco.
- **64 bits deixou de ser inferência** e virou medição (`IntPtr.Size = 8`).
- **A linha de comando não mudou** entre 3.63 e o MasterTool X, e os probes
  read-only já aprovados rodaram sem uma linha alterada.
- O que impede W1 hoje não é falta de API nem falta de evidência: é o contrato
  `docs/28` e o gate `READ_ONLY_PHASE` em
  `scripts/mastertool/common/safety.py`, que permanece `True`.

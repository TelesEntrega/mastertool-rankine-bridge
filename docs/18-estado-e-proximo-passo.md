# Onde paramos — 2026-07-31

Ponto de retomada. Este documento existe para alguém (ou algum agente)
conseguir continuar sem reler o histórico inteiro.

**Ele é o documento canônico de retomada.** Se estiver desatualizado, toda
retomada começa errada — por isso é atualizado no mesmo slice que muda o
estado, nunca depois.

## Estado em uma linha

A trilha de **extração e inventário de dispositivos está encerrada** e a
prioridade do projeto **mudou**: o marco corrente é a **autoria controlada de
objetos no MasterTool X** (`MasterTool X controlled project authoring`). **Três
**W1 está COMPLETO: o
sistema cria, preenche, persiste e compila um projeto lógico em ST sobre o
projeto-base real do cliente** (`docs/37`).** A semântica simbólica
Ladder (L5) **não é mais o caminho crítico** — vai para o backlog com o
contrato `docs/21` intacto.

## O que já foi provado no MasterTool X

| Marco | Capacidade | Estado | Registro |
|---|---|---|---|
| W1.1 | `create_gvl` + `save_as` | **executado e aprovado** | `docs/29` |
| W1.2 | `create_program` (ST) + `save_as` | **executado e aprovado** | `docs/30` |
| W1.3A | `replace` (GVL) + `save_as` | **executado e aprovado** | `docs/33` |
| W1.3B | `replace` ×2 (PROGRAM) + `save_as` | **executado e aprovado** | `docs/34` |
| W1.5 | medir nascimento de FB e FUNCTION | **executado e aprovado** | `docs/35` |
| W1.4 | criação + escrita + `build` | **EXECUTADO E APROVADO** | `docs/37` |
| W2 | Program Call + verificação por build | **EXECUTADO E APROVADO** | `docs/39` |

**W1 ESTÁ COMPLETO.** A `run-019` provou, sobre o projeto-base **real** do
cliente, que o sistema **cria, preenche, persiste e compila** um projeto
lógico em ST no MasterTool X — `integration_verified`, 0 erros e 0 avisos,
árvore 42 → 44 nós com exatamente os dois objetos previstos.

**W2 fechou o Program Call**: o `PRG_AI_TESTE` está vinculado à `MainTask`, o
vínculo persiste à reabertura e o build continua verde. Mas o build trouxe um
**aviso do fabricante** que muda o desenho da fábrica: *"A tarefa MainTask
deveria conter apenas a chamada do programa MainPrg"* — o idiomático é chamar
os demais POUs **de dentro** do programa de entrada. Capacidade provada;
padrão recomendado é outro (`docs/39`).

**O que ainda não foi provado:** `FUNCTION_BLOCK`, `FUNCTION` e DUT têm texto
de nascimento medido (W1.5) mas **nunca passaram por uma cadeia com build**;
`create_task` nunca foi exercido; DUT segue bloqueado por falta de catálogo do
enum `DutType`; as 17 bibliotecas são todas *placeholder* e nenhum build fixa
para que versão resolvem; e **determinismo nunca foi medido** — a mesma
especificação não foi executada duas vezes sobre cópias novas.

**Nenhuma fase de escrita está aberta.** `CONTROLLED_WRITE_PHASE = None` e
`READ_ONLY_PHASE = True`. Abrir a próxima é decisão humana em commit isolado
(`docs/28` §14).

## Posição exata

| | |
|---|---|
| Branch | `main`, árvore limpa |
| `HEAD` | `e7b1873` |
| Baseline Ladder | tag `v0.2.0-ladder-structure` em `efebe1f` (anotada) |
| Baseline imutável | tag `v0.1.0` em `8eddcb7` (nunca alterar) |
| Remote | **nenhum, por arquitetura** — ver §Publicação |
| Repo público | `github.com/TelesEntrega/mastertool-rankine-bridge` (Apache-2.0, sanitizado, fluxo separado) |

### Commits depois da tag `v0.2.0-ladder-structure`

| Commit | O que fechou |
|---|---|
| `41c54db` | `tools/verify_plcopen_export_smoke.py` — verificador reutilizável de uma run de export já concluída, read-only, run sempre por `--run-dir` |
| `989b386` | `write_json_via_temp` / `write_text_via_temp` (antes `*_atomic`): o nome deixa de prometer atomicidade que IronPython 2.7 não entrega |
| `fb51f78` | `docs/20-contrato-topologia-logica.md` — contrato normativo, nenhuma linha de código |
| `8dc3f82` | `plcopen/logical_topology.py` + `tests/unit/test_logical_topology.py` |
| `baf6b41` | `docs/21-contrato-semantica-ladder.md` — contrato da camada L5, documento apenas |
| `36cb0c2` | `probes/21_scan_project_tree_full.py` + `common/probe_cli.py` — varredura completa da árvore, read-only, limites por argumento (`docs/22`) |
| `02fe936` | `probes/25_export_devices_individually.py` + `common/device_export_inspection.py` — export PLCopen dispositivo a dispositivo (`docs/23`) |
| `5d05f82` | `probes/22` e `probes/23` — investigação da API de parâmetros de dispositivo, caminho **descartado com evidência** (`docs/24`) |
| `9a405eb` | `inventory/device_inventory.py` + `tools/build_device_inventory.py` — inventário determinístico offline (`docs/25`) |
| `40e9c1d` | `docs/26` — compatibilidade 3.63 × 3.70 e o defeito do serializador monolítico |

### Commits da trilha MasterTool X

| Commit | O que fechou |
|---|---|
| `b8ad7bb` | **correção crítica**: `assert_operation_allowed` falhava **aberto** para todo nome fora da lista legada — registro literal de 41 mutadores + porta única |
| `e95db31` | `common/authoring_text.py` — primitivas puras de verificação de autoria |
| `82b73ba` | `src/mastertool_bridge/spec/` — modelo declarativo `project_spec` (schema + validador offline) |
| `a7f2e94` | `docs/32` — plano de W1.4 (autoria integrada + `build`) |
| `6209d45` | probes 31/32 + wrapper de W1.3A |
| `c61b1c2` | probes 33/34 + wrapper de W1.3B |
| `c5a1f2c` | **baseline de testes restaurada**: `pytest-asyncio` declarado, teto `mcp<2` |
| `387a27a` | docstring de `test_mcp_server_e2e.py` corrigida |
| `6001aea` | **abertura** do gate `W1_3A_EDIT_GVL` (commit isolado) |
| `bc23d4b` | `session-verdict.json` sem BOM nos quatro wrappers + guarda de codificação |
| `59e8637` | **compiler version MEDIDA** (`3.5.18.50`) — e a descoberta dos stubs `.pyi` versionados pelo produto |
| `a3b17f9` | **inventário de 17 bibliotecas MEDIDO**, conferido por duas rotas |
| `a9dd252` | as duas medições ligadas ao probe 35 → `TemplateExemplo v1` **elegível para autoria** |
| `1e3ee0e` | mensagens de build lidas por `system.get_message_objects` + `system.exit(0)` fecha a janela |

## Números

Medidos em 2026-07-31, nesta árvore:

| | |
|---|---|
| Suíte completa | **3354 passed, 1 skipped, 0 failed** |
| Interpretador | `.venv\Scripts\python.exe`, provisionado por `pip install -r requirements-dev.txt` |
| O único skip | `test_strict_representation.py:112` — `unicode` não existe em CPython 3; o comportamento real só é testável em IronPython 2.7 |
| Lint mecânico | `ruff` não instalado; decisão explícita de não instalar por iniciativa própria |

Armadilhas de medição, para quem for repetir:

- **O Python base da máquina não é fonte válida de dependência.** Durante um
  período, `pytest-asyncio` existia só em `C:\Program Files\Python311` e
  faltava na `.venv`, e a suíte fechava em `7 failed` — sem que nenhum arquivo
  do repositório dissesse que o pacote era necessário. Rode pela `.venv`
  provisionada pelos manifests; a guarda está em
  `tests/unit/test_test_infrastructure.py`.
- **Ler a linha inteira do pytest.** `2199 passed` sem o prefixo `7 failed` é
  relato incompleto, e foi cometido em `e95db31` e `82b73ba` (corrigido para a
  frente em `a7f2e94`, sem reescrever histórico).
- `pytest` precisa rodar **com o cwd na raiz do repo**. Executado do diretório
  pai, ele coleta também o repo sanitizado vizinho e morre com 49 erros de
  coleta — isso é ambiente, não regressão.
- `addopts = "-q"` já está em `pyproject.toml`. Passar `-q` de novo vira `-qq`
  e o pytest **suprime a linha de resumo**: a suíte parece não reportar
  contagem nenhuma.
- **Teste verde não é evidência até falhar quando deve.** Duas guardas escritas
  nesta trilha só valeram alguma coisa depois de falsificadas de propósito, e
  uma delas (`OPERACOES_AINDA_PROIBIDAS` × registro) reprovou na primeira
  execução, revelando quatro APIs mutáveis que ninguém verificava.

## O que existe hoje

**Structured Text** — cadeia completa e validada em duas execuções reais:
árvore → export textual → parser ST → símbolos/DUT → referências → read/write
→ chamadas → consultas determinísticas → API Python → servidor MCP.

**Ladder** — estrutura e topologia concluídas, semântica **em backlog**:

```text
export_xml(stPath, False, False, False)
→ PLCopen XML tc6_0200 (arquivo único, sem extensão)
→ structure_map.py       (schema real observado)
→ ladder_parser.py       (parse_ladder: structure_map -> GraphicPOU)
→ canonical_model.py     (tipos + invariantes + serialização)
→ logical_topology.py    (derive_logical_topology: GraphicPOU -> LogicalTopology)
→ [BACKLOG] semântica simbólica (docs/21) — leituras, escritas, chamadas
→ [BACKLOG] unificação com o índice ST (Fase L6)
```

**Dispositivos — trilha ENCERRADA** (`docs/22` a `docs/26`):

```text
probes/21  varredura completa da arvore, read-only, limites por argumento
probes/25  export PLCopen dispositivo a dispositivo
probes/22  elo device_parameters existe e e alcancavel
probes/23  ... e vem VAZIO em todos: caminho descartado com evidencia
inventory/ inventario determinista offline, duas camadas, sete saidas
```

**Runner supervisionado** — cinco operações integradas e mutuamente
exclusivas: `probe_ladder_surface`, `probe_ladder_dynamic_surface`,
`probe_ladder_extender_surface`, `probe_plcopen_export_signature`,
`export_plcopen_xml`. Núcleo comum em
`scripts/mastertool/common/artifacts.py`. Os probes 21–25 são runners finos
independentes desse conjunto, com CLI própria em `common/probe_cli.py`.

## O que a trilha de dispositivos estabeleceu

Registro do que fica valendo depois de encerrada:

1. **O `export_xml` do projeto inteiro é um serializador monolítico e falha em
   silêncio.** Duas exportações independentes, modos diferentes, 42 minutos de
   intervalo, abortaram no mesmo nó sem fechar `</project>`. Um arquivo de 9 MB
   parecia pronto e não era; 1636 `<Parameter>` se perdiam por causa de quatro
   dispositivos.
2. **Isolar por dispositivo transforma bloqueio total em lacuna declarada.** A
   mesma falha vira quatro `Exception("No devdesc installed for '<nome>'")`
   nomeados, e os demais dispositivos exportam normalmente.
3. **Cobertura final 35/35.** Primeira coleta: 35 dispositivos, 31 exportados,
   1742 parâmetros. Instalada a device description que faltava (WEG CFW500,
   `853_2_3072_4` — um único EDS resolveu os quatro adaptadores), os quatro
   passaram a exportar: **35 de 35**, 1894 parâmetros, mais do que o export
   monolítico chegou a escrever antes de morrer. Nenhum dado de cliente foi
   versionado — só método, regras, testes com fixtures sintéticas e
   documentação.
4. **A API de parâmetros não substitui o export XML.** `device_parameters`
   existe, tem o tipo correto e devolve `Count = 0` em todos os dispositivos,
   enquanto o export dos mesmos dispositivos, no mesmo instante, traz milhares
   de parâmetros com valor. Resultado vazio ≠ ausência de configuração.
5. **`object_guid` não é identidade estável entre sessões.** Comparar
   varreduras por ele produz mudança fantasma; `name` e `type_guid` se
   mantiveram estáveis nos 194 nós.
6. **A API de scripting não mudou entre 3.63 e 3.70** — catálogo estático byte
   a byte idêntico, 859 membros públicos de `ScriptDriverDeviceObject` com as
   mesmas chaves. O que muda entre versões é o **repositório de dispositivos**,
   que é por versão instalada.

O ponto 6 vale para 3.63 × 3.70 e **não** se estende ao MasterTool X: é
exatamente isso que W0 vai medir.

## Artefato de referência da POU real

Todas as contagens de POU real, em qualquer camada, são medidas **sobre este
artefato** e só valem quando ele confere:

```text
run          2026-07-29_10-14-54
arquivo      output/plcopen-export/export-root/pou-export
tamanho      25.226 bytes
sha256       c692040c39cc7bf656edd551d2ffdd1b41fecaa198b56b3182bd5149e1aeca13
```

**Reconferido em 2026-07-31**: presente nesta máquina, em
`C:\mastertool-bridge-runs\2026-07-29_10-14-54\`, com tamanho e SHA-256
idênticos aos registrados. Portanto os testes de POU real estão efetivamente
rodando aqui, não pulando — o único skip da suíte é o do `unicode`.

Há **duas** ligações a export real nos testes, em runs diferentes, e as duas
existem nesta máquina:

| Teste | Run |
|---|---|
| `test_logical_topology.py:494` | `C:\mastertool-bridge-runs\2026-07-29_10-14-54\` (o artefato de referência acima) |
| `test_plcopen_ladder_parser.py:25` | `workspace\exports\2026-07-28_13-48-49_20_validate_controlled_plcopen_export\` |

Os dois arquivos têm os mesmos 25.226 bytes e **hashes diferentes**: cada
execução do export carimba um `creationDateTime` novo no `<fileHeader>`, e essa
é a única linha que difere (`docs/23`). Hash diferente entre runs é esperado;
hash diferente **na mesma run** seria achado.

O arquivo nunca entra no repositório (nomes de equipamento, variáveis e lógica
do cliente); só o hash entra, e ele não é reversível.

Números já verificados sobre ele:

| Camada | Medida |
|---|---|
| Canônico | 42 elementos (nenhum `unknown`), 40 pinos declarados, 32 evidências = 29 `plcopen_connection` + 3 `vendor_parallel_branch`, 4 redes todas `confirmed_by_marker_and_connectivity`, 8 elementos não atribuídos |
| Topologia | 4 redes, 66 nós, 26 arestas, 6 conexões não resolvidas (todas `unassigned_element_connection`), 0 diagnósticos `error`, 32/32 evidências referenciadas, nenhum ciclo |

Divergência entre estes números e uma execução futura é **achado**, nunca alvo
a ser forçado nem expectativa a ser ajustada.

## Próximo marco — `MasterTool X controlled project authoring`

O objetivo passa a ser **criar e alterar objetos de projeto de forma
controlada** dentro do MasterTool X instalado nesta máquina — POUs, GVLs e,
depois, os demais objetos.

O primeiro marco **não** é "gerar um projeto completo". É:

> criar uma GVL e uma POU ST vazias num projeto descartável, preencher
> conteúdo mínimo, salvar, reabrir e provar que **somente** as mudanças
> autorizadas ocorreram.

A verificação usa o analisador somente leitura que já existe (varredura da
árvore, export textual, export PLCopen, índice ST) como **mecanismo de prova**
do que mudou — não se escreve nada que este lado não consiga verificar depois.

### Cadeia completa pretendida

```text
descobrir API de escrita do MasterTool X
→ criar objeto vazio
→ preencher conteudo ST
→ salvar copia
→ reabrir
→ validar estruturalmente
→ compilar
→ comparar antes/depois
→ implementar rollback
```

### Marcos

| Marco | Escopo | Estado |
|---|---|---|
| **W0** | reconhecimento: versão real, ScriptEngine, runtime, assemblies, diferença de superfície contra 3.70, compatibilidade dos probes read-only, catálogo estático de APIs candidatas de escrita. **Nenhum método mutável é chamado** | **CONCLUÍDO** — estática e runtime (`docs/27`); gate read-only aprovado em 2026-07-31 |
| **W1.1** | criar GVL vazia e persistir por `save_as` | **ENCERRADO E APROVADO** em 2026-07-31 |
| **W1.2** | criar `PROGRAM` ST vazio | **ENCERRADO E APROVADO** em 2026-07-31 |
| **W1.3** | escrever declaração e implementação | não iniciado |
| **W1.4** | sequência completa + `build` offline + diff | não iniciado |
| **W2** | conteúdo textual: declaração da GVL, declaração + implementação da POU, save-as, fechar, reabrir, exportar, verificar árvore/nomes/tipos/conteúdo, compilar offline | não iniciado |
| **W3** | transação segura: plano em JSON, hash do projeto-base, cópia de trabalho, precondições, aplicação, diff estrutural, compilação, validação read-only, confirmação humana, promoção, rollback | não iniciado |
| **W4** | objetos adicionais: DUTs, enums/structs, PersistentVars, métodos e propriedades de FB, ações e transições, tasks e program calls, bibliotecas, referências, criação em projeto existente | não iniciado |
| **W5** | Ladder/FBD — depois de ST. Criar LD exige preservar elementos, `localId`, pinos, conexões, redes, extensões do fornecedor, posições, branches e a serialização PLCopen | não iniciado |

A semântica Ladder do backlog volta a ser útil em W5 como **validador da
lógica criada**, não como entregável independente.

### Duas rotas de escrita, ambas a investigar

| Rota | O que é | Onde tende a servir |
|---|---|---|
| **A — API nativa** | criar POU/GVL/pasta, acrescentar objeto, definir linguagem, declaração e implementação, renomear, remover, save-as, compilar/verificar | ST e GVL, quando comprovada |
| **B — importação controlada** | importação PLCopen, importação de objetos/GVL, fragments/templates, clonagem de objeto conhecido, criação por XML intermediário validado | Ladder, onde montar o grafo inteiro pela API é mais arriscado que importar XML validado |

Não limitar a pesquisa a uma única técnica. Há evidência pública oficial de que
script Python escreve declarações numa GVL existente **por importação** — isso
comprova capacidade de modificação, e **não** comprova qual API cria o objeto
GVL ou uma POU nova.

## W0 — o que precisa ser medido

- versão exata do executável instalado (file version e product version);
- arquitetura (64 bits);
- versão do `ScriptEngine`;
- runtime Python e `sys.version`;
- assemblies de scripting carregados;
- **qual versão real está sendo chamada de "X4.1"** — a designação vem do
  atalho e do diretório, e precisa ser confirmada pelo executável e pelos
  assemblies;
- diferença da superfície pública de scripting contra o MasterTool 3.70;
- se os probes read-only já aprovados continuam funcionando;
- catálogo estático de APIs candidatas de criação e edição.

Para cada candidato: assembly, versão, tipo declarador, assinatura, retorno,
parâmetros, getter/setter, interfaces, evidência, potencial de mutação,
precondições, riscos e se existe equivalente conhecido em 3.70.

Somente reflection/metadados e inspeção estática. **Nenhum método mutável é
invocado em W0.**

### W0 concluído — sessão supervisionada de 2026-07-31

Seis execuções, UI visível, offline, sobre cópia descartável em diretório
isolado. **Nenhum diálogo, zero processos órfãos, SHA-256 da cópia idêntico nas
seis.** Detalhe em `docs/27` §9.

- **A linha de comando não mudou**: `--runscript=`, `--scriptargs:` e
  `--project=` funcionam na mesma forma do 3.63. O `--scriptargs` continua
  quebrando o valor em espaço em branco — agora medido no MasterTool X;
- **64 bits deixou de ser inferência**: `IntPtr.Size = 8`,
  `Is64BitProcess = True`, e o módulo real do processo prova que a execução foi
  na instalação **4.1.0**, não na 4.0.0;
- runtime: `sys.platform` `cli`, `version_info` **2.7.12**, banner
  `MT9000.exe Mastertool X 4.1.0.11, ScriptEngine.plugin 4.2.0.0`;
- 792 assemblies no AppDomain, 36 de scripting, todos coerentes com a reflexão
  estática. Núcleo CODESYS em **3.5.18.60**;
- **`probes/15` e `probes/21` rodaram sem uma linha alterada** e o scan
  concluiu: `complete`, 3 raízes, 34 nós, profundidade 6, 0 erros;
- declaração de segurança do artefato real: `object_creation`,
  `object_modification`, `project_save`, `device_repository_access`,
  `online_access`, `download`, `force` — todos `false`.

Dois achados de método que viraram regra no contrato: **valor de teste igual ao
default não é evidência** (limites coincidiram com os defaults e tornaram a
primeira medição inconclusiva — corrigido gravando `argv` cru no manifesto,
`schema_version` 1.1, e repetindo com `--max-depth=7 --max-total-nodes=1234`); e
**abrir um projeto cria `.opt` irmãos**, o que obriga o diff estrutural a
comparar o `.project` e não a pasta.

### Resultado da metade estática — resumo

Detalhe completo em [`27-reconhecimento-mastertool-x.md`](27-reconhecimento-mastertool-x.md):

- `MT9000.exe` **`4.1.0.11`** — a designação "X4.1" está confirmada pelo
  executável, não presumida do atalho;
- runtime de script **inalterado**: IronPython **2.7.12**, o mesmo do 3.70 —
  os probes continuam tendo de ser Python 2.7 válido;
- assemblies de scripting **4.1.0.0 → 4.2.0.0**, mas a mudança é **aditiva**:
  nas 15 sementes que o projeto usa, 141 × 140 membros, **uma** sobrecarga a
  mais e **nada removido nem com assinatura alterada**;
- na varredura ampla (304 × 312 tipos, 1.544 × 1.616 membros), das 126 remoções
  112 são `DocuDumper`; as únicas funcionais são `dump_scripting_api`,
  `ISystemForPatches`, os dois diálogos de senha e `ScriptDebuggingMode`;
- **a rota A existe e é tipada**: `create_gvl`, `create_pou`, `create_dut`,
  `create_folder`, `create_persistentvars` (todos idênticos ao 3.70) e os novos
  `create_program`, `create_function`, `create_function_block`; linguagem por
  **GUID** de `IScriptImplementationLanguages`, nunca por string; conteúdo
  textual por `IScriptTextDocument` (a propriedade não tem setter); `save_as` e
  `build` disponíveis;
- **a rota B também existe**, com `ConflictResolve` explícito;
- três riscos novos entram na lista proibida do contrato:
  `ScriptPromptHandling.SuppressPrompts`, `download_missing_libraries` e
  `set_compilerversion_to_newest`; e **objeto transiente** é conceito novo que
  o diff estrutural precisa tratar.

O contrato de escrita controlada passa a ser **`docs/28`**: a evidência de W0
ficou volumosa o bastante para ter documento próprio, e o contrato não pode ser
fechado antes da metade de runtime.

### Medições preliminares já feitas (metadados de arquivo apenas)

Feitas fora do MasterTool, lendo apenas metadados do sistema de arquivos —
nenhum processo lançado, nenhum assembly carregado:

```text
atalho   "Mastertool X 4.1.0.lnk"  (o caminho do atalho muda; resolver sempre)
alvo     C:\Program Files\Altus\MT9000 4.1.0\MT9000\Common\MT9000.exe
exe      MT9000.exe   <- NAO e mais MT8500.exe
versao   FileVersion 4.1.0.11   ProductVersion 4.1.0.11   Product "Mastertool"
local    Program Files (64 bits), nao Program Files (x86)
vizinhos ScriptEngine.dll, ScriptEngine2.dll, ScriptEngine3.dll no mesmo Common\
```

Instalações presentes nesta máquina, que o W0 vai usar como base de comparação:

```text
64 bits   MT8500 3.70, 3.71, 3.75, MT9000 4.0.0, MT9000 4.1.0
32 bits   MT8500 3.50, 3.51, 3.52, 3.61, 3.62, 3.63, 3.70, 3.71, 3.75
```

Duas consequências imediatas: o nome do executável mudou de `MT8500.exe` para
`MT9000.exe` — toda invocação documentada nos `docs/15`, `docs/22` e `docs/23`
usa `MT8500.exe` e **não vale como está** para o MasterTool X; e os assemblies
de scripting **não** têm mais o sufixo `.plugin` no nome de arquivo dos três
`ScriptEngine`. Nada disso autoriza concluir que a superfície de API é a mesma
ou diferente — isso é medição de W0.

### Compatibilidade read-only, em projeto descartável

Com UI visível e offline, executar **apenas** probes já aprovados que não
escrevem: identidade do runtime, enumeração de raízes, scanner recursivo e —
se comprovadamente compatível — export mínimo. Registrar hash antes e depois,
árvore, erros, diálogos, processos órfãos e a divergência contra 3.70.

### Ao fim de W0, parar

Sem implementar escrita, apresentar: versão real do MasterTool X, diferenças de
API, APIs candidatas, riscos, resultado dos probes read-only, contrato
proposto, diff, gates e árvore de trabalho.

## O contrato — `docs/28`, ESCRITO

`docs/28-contrato-escrita-controlada-mastertool-x.md` está fechado quanto ao
gate read-only e **aberto quanto à escrita**: ele não autoriza mutação nenhuma.
Define projeto descartável obrigatório, proibições permanentes (incluindo as
três APIs novas — `SuppressPrompts`, `download_missing_libraries`,
`set_compilerversion_to_newest`), allowlist **literal** sob a regra "API não
catalogada é proibida", plano de alteração prévio, `save_as` obrigatório, o
analisador read-only como juiz da verificação, rollback pelo **projeto
inteiro** (porque `create_*` devolve o objeto já inserido, sem passo de
confirmação), critérios de aborto e trilha de auditoria.

## W1.1 — ENCERRADO E APROVADO em 2026-07-31

**A primeira escrita controlada no MasterTool X aconteceu, e a persistência
está provada por reabertura independente.** Deixou de ser prova de API: é
capacidade operacional auditada.

| | |
|---|---|
| `HEAD` da sessão | `8e7813d00ca47fff93f36932369b0af0d659cde6` |
| Projeto-base e cópia de trabalho | `6183d01dcae9091a531a698afe794a3cbbf8f7882c921a67aeecfa9db5540dd3` — **antes e depois** |
| Saída `W1-A1.project` | `a0460e8272b8e48604daedaebe3c20776daa0fd949f4ebdb12d242460dbe0614` |
| Diff | exatamente **+1** objeto persistente: `GVL_AI_TESTE` |
| Alterações inesperadas | nenhuma |

O projeto de entrada ficou **byte a byte intacto**: `save_as` gravou em arquivo
novo e `save()` nunca foi chamado.

### As três execuções

| Run | Resultado | O que estabeleceu |
|---|---|---|
| **run-001** | preflight **reprovado com segurança** | causa: o probe lia `type_guid` do objeto em vez de `object.type`. Nenhuma mutação, hash intacto, nenhum diálogo, zero órfãos. Evidência preservada — é a prova de que o sistema falha fechado antes de qualquer escrita |
| **run-002** | `preflight_passed` | **o `Application` expõe `create_gvl` diretamente**, membro `callable`, sem `Extender`, cast ou reflexão. Nenhuma mutação, hash intacto |
| **run-003** | `saved_as` + `postsave_verified` | `create_gvl("GVL_AI_TESTE")` uma vez, `save_as` uma vez, nenhum outro mutador solicitado; entrada intacta, saída criada, reaberta de forma independente, diff exatamente dentro da allowlist |

As três permanecem preservadas fora do repositório. `run-001` não é lixo: é a
única evidência de reprovação segura que a trilha produziu.

### O texto canônico de uma GVL vazia

Lido do documento que o **próprio MasterTool** gerou:

```iecst
{attribute 'qualified_only'}
VAR_GLOBAL
END_VAR
```

SHA-256 textual `fd27fd816bdf9d2116403f691bcb84694119b3553b1067619bb9b96dd310affb`,
3 linhas. Três fatos que decidem W1.3:

1. **o documento contém o bloco completo**, não apenas o corpo interno;
2. **o pragma é gerado automaticamente** pelo MasterTool, não foi pedido;
3. portanto, substituir só por `VAR_GLOBAL … END_VAR` **apagaria o pragma**, e
   inserir outro `VAR_GLOBAL` dentro do documento **aninharia** o bloco.

Era exatamente a pergunta que `docs/29` mandou responder por leitura antes de
escrever. Foi respondida sem escrever nada.

### Identidade de GVL, agora medida

```text
type_guid == ffbfa93a-b94d-45fc-a329-229860183b1d
```

O mesmo `type_guid` das GVLs que já existiam no projeto (`Qualities`,
`ReqDiagnostics`, `Disables`, `System_Diagnostics`, `IOQualities`…). A
verificação de tipo deixa de ser heurística: o critério principal passa a ser o
GUID, e `has_textual_declaration and not is_folder` fica como **fallback
conservador**, evidência auxiliar e nunca identidade definitiva.

### Estado do gate depois de W1.1

A fase cumpriu o seu papel e **não deve continuar autorizada**. O fechamento é
slice próprio, isolado, que zera a fase controlada mantendo `READ_ONLY_PHASE`
em `True` e o registro histórico intacto.

## W1.2 — ENCERRADO E APROVADO em 2026-07-31

**As duas capacidades de criação estão provadas.** O sistema cria GVL e cria
POU no MasterTool X 4.1, e em ambos os casos a persistência é confirmada por
reabertura independente — não por declaração da própria operação.

| | |
|---|---|
| Projeto-base e cópia de trabalho | `6183d01d…5540dd3` — **antes e depois** |
| Saída `W1-A2.project` | `67092e58229a801badaba70bc8f097aecdabc3be5e86ad63ece52a8081a1e2a1` |
| Diff | exatamente **+1**: `PRG_AI_TESTE` |
| GUID da linguagem ST | `cc393387-a21c-4f68-a3e3-84c36951965d` |
| `type_guid` do POU criado | `6f9dac99-8de1-4efc-8465-68ac443b7d08` |

### As três execuções

| Run | Resultado | O que estabeleceu |
|---|---|---|
| **run-004** | `preflight_passed` | o `Application` expõe **`create_program`** callable, sem `Extender` nem cast; e o **GUID de ST veio medido** do global `ImplementationLanguages` — segundo candidato da lista literal, não o primeiro |
| **run-005** | `create_program_failed` | `TypeError: expected Nullable[Guid], got str`. Falha **antes** de tocar o projeto: nenhuma mutação, nenhum arquivo |
| **run-006** | `saved_as` + `postsave_verified` | `create_program` uma vez, `save_as` uma vez, nenhum outro mutador; entrada intacta, saída reaberta, diff dentro da allowlist |

Nas três: nenhum diálogo, **zero órfãos**, `.opt` confinados. As janelas de
`run-006` foram fechadas pelo próprio host por `CloseMainWindow()` — 19 s, 19 s
e 17 s — e nunca por `Stop-Process`.

### O texto canônico de um `PROGRAM` recém-criado

Medido depois de `create_program` e antes de `save_as`, como o plano exigia:

```iecst
PROGRAM PRG_AI_TESTE
VAR
END_VAR
```

SHA-256 textual
`6a2401fa5915a354eae0895d290e4bb6d3483c4d3ca4e05cb7e5b230f4435841`, 4 linhas.
Implementação **vazia** (`e3b0c442…b855`, o hash da string vazia).

Duas diferenças que só a medição revelaria:

1. **não há pragma** — ao contrário da GVL, que nasce com
   `{attribute 'qualified_only'}`;
2. **não há comentário de cabeçalho** — os POUs do projeto-base têm um, mas ele
   vem do **template Altus**, não do objeto novo. Tratar o texto de um POU
   preexistente como "o canônico de um recém-criado" teria produzido conteúdo
   errado em W1.3.

### Dois defeitos encontrados pela execução

**`run-005` — o GUID não pode viajar como texto.** O plano transporta string
(JSON não tem tipo `Guid`) e o IronPython não converte sozinho; a API exige
`Nullable<Guid>`. A conversão passou para a fase de **precondição**, via
`System.Guid`, nunca entre a guarda e a chamada. Falha de conversão é
`precondition_failed`, não `create_program_failed` — a distinção importa porque
uma nem chegou a pedir autorização.

**`run-006` — artefato que se contradizia.** O `completion` de um postsave
**aprovado** declarava `is_success: False` ao lado de
`status: postsave_verified`, porque o campo comparava só com
`preflight_passed`. O veredito da sessão não dependia dele, mas a evidência
arquivada sim — e é ela que sobrevive à sessão. Um artefato que se contradiz é
pior que um omisso: quem lê acredita no campo errado.

### Gate depois de W1.2

A fase cumpriu o seu papel e **foi encerrada em commit isolado**, como em W1.1.
`READ_ONLY_PHASE` permanece `True` e nenhuma operação mutável fica autorizada.

## Projeto-base trocado em 2026-07-31

O usuário acrescentou **cartões de I/O** ao projeto e determinou que ele passa a
ser a base a partir de agora.

| | Base anterior | **Base nova** |
|---|---|---|
| Arquivo | cópia de `TemplateExemplo v1` sem I/O | `TemplateExemplo v1.project` |
| Tamanho | 287.152 bytes | **503.040 bytes** |
| SHA-256 | `6183d01d…5540dd3` | `596625796e4efd54d3cc2d6286e858b683f0f58de66ab9a36eed532dd1d815f5` |
| Classificação | projeto sintético mínimo com NX3008 | projeto sintético com NX3008 **e cartões de I/O configurados** |

### O que isso invalida

Tudo o que foi medido sobre a estrutura da base anterior, e **presumir
continuidade seria o erro que este projeto não comete**:

```text
3 raizes                      34 nos
structure_sha256 b2825550...  node_path root/1/0/0  <- o mais critico
type_guid do Application
```

O `node_path` é caminho de **índices**. Cartões de I/O mudam a árvore sob o
`Device`, e um índice deslocado faz `root/1/0/0` deixar de apontar para o
`Application`. O preflight abortaria com `container_not_found` — comportamento
certo, motivo evitável.

**Antes de qualquer execução nova**: varredura read-only com `probes/21` sobre
cópia descartável, e recongelamento dos números.

### O que continua valendo

`W1-A1.project` e `W1-A2.project` seguem válidos como fixtures de W1.3: são
saídas **congeladas e autocontidas**, e o que W1.3 testa nelas é `replace`, não
a base de origem. A procedência delas é a base anterior, e isso fica registrado
em vez de escondido.

W1.1 e W1.2 permanecem encerrados e aprovados — eles provaram capacidades, não
propriedades de um arquivo específico.

**W1.4 é o marco afetado**, porque parte do projeto-base.

## W1.3A — ENCERRADO E APROVADO em 2026-07-31

Registro completo em [`docs/33`](33-execucao-w1-3a-edicao-gvl.md). Em uma
linha: **`replace` sobre `IScriptTextDocument` cria texto que sobrevive a
`save_as` e a uma reabertura independente**, sem alterar a árvore.

| | |
|---|---|
| Entrada (fixture imutável) | `W1-A1.project`, `a0460e82…be0614`, intacta ao fim |
| Saída | `W1-A3.project`, 288.256 bytes, `f7d9d819…bc9847a1` |
| Texto final (SHA-256) | `71f8079f…d261a017c` |
| Mutações | exatamente **1** `replace` e **1** `save_as` |
| Árvore | 9 filhos antes e depois; diff estrutural com quatro listas vazias |
| Sessões | 3 execuções, zero diálogos, zero órfãos |

Três coisas que a execução acrescentou:

- **A árvore não muda quando só o texto muda** — 9 filhos antes e depois do
  `replace`. Edição textual e criação de objeto são efeitos disjuntos na API.
- **`save_as` não toca a entrada** — a cópia de trabalho saiu da sessão com o
  SHA-256 com que entrou, o que torna a cópia descartável reutilizável como
  evidência, e não só como insumo.
- **O pragma `qualified_only` sobrevive à substituição**, porque o `replace`
  recebe o documento inteiro e o texto canônico o inclui. Consequência direta
  para W1.4: a referência `GVL_AI_TESTE.g_xTesteCriacao` continuará
  **obrigatoriamente** qualificada.

## W1.3B — ENCERRADO E APROVADO em 2026-07-31

Registro completo em [`docs/34`](34-execucao-w1-3b-edicao-program.md). Em uma
linha: **os dois documentos de um PROGRAM são editáveis na mesma sessão e ambos
persistem**, por três mutações e um único `save_as`.

| | |
|---|---|
| Entrada (fixture imutável) | `W1-A2.project`, `67092e58…a1e2a1`, intacta ao fim |
| Saída | `W1-A4.project`, 288.656 bytes, `b220611e…a2076176` |
| Declaração | `6a2401fa…435841` → `6e4b13ab…dfa80f5` |
| Implementação | `e3b0c442…7852b855` (string vazia) → `313cdb1f…1347d517` |
| Mutações | **2** `replace` + **1** `save_as` |
| Árvore | 9 filhos antes e depois; diff estrutural vazio, conferido duas vezes |

**Dois dos quinze critérios ficaram NÃO VERIFICADOS**, e a distinção importa —
não falharam, não há evidência de nenhum lado:

- *"nenhum outro PROGRAM alterado"* — `get_children(False)` devolve **só
  filhos diretos**. A comparação cobre o nível do `Application`; POUs dentro de
  `UserPOUs`/`SystemPOUs` ficaram de fora. Instrumento que resolveria:
  `probes/21`, com varredura recursiva.
- *"linguagem continua ST"* — **não existe API catalogada que leia a linguagem
  de um objeto**. `language` só aparece como parâmetro de entrada dos
  `create_*`. Pior: `probes/33` define `EXPECTED_ST_LANGUAGE_GUID` e **nunca a
  usa** — constante morta, que lê como cobertura sem cobrir. O caminho certo é
  o `build` de W1.4: ST que compila é ST.

O que separa B de A não é o alvo, é o objeto sob teste: um PROGRAM tem
declaração **e** implementação, o que dá três mutações por sessão em vez de
duas e admite um estado que W1.3A não consegue produzir — **um documento
gravado e o outro não**. As canônicas divergem no detalhe que mais engana: a
declaração nasce **com** quebra final (`6a2401fa…435841`), a implementação
nasce **vazia** (`e3b0c442…7852b855`, o sha da string vazia).

### O bloqueio atual NÃO é mais W1.3 — é a elegibilidade do template

O `TemplateExemplo v1.project` foi qualificado read-only em `run-010`/`run-011`
([`docs/36`](36-qualificacao-template-template-exemplo-v1.md)). Resultado: **medido e NÃO
elegível para autoria**, com dois bloqueadores nomeados.

| | |
|---|---|
| Árvore | 3 raízes, 42 nós; original intacto, cópia intacta |
| `Application` | `root/1/0/0`, match único — **medido por busca**, não presumido |
| Conflito de nome | nenhum |
| `compiler_version` | **`unresolved`** — falta o acessor de `IScriptProjectSettings2` |
| `libraries` | **`resolved_but_empty`** — o nó existe e devolve zero filhos |
| `authoring_eligible` | **`false`** |

`root/1/0/0` continuar valendo apesar dos cartões de I/O é resultado, e não
confirmação de suposição: presumir teria acertado **por sorte**. O probe
resolve o container por busca e reporta o que achou.

**W1.4 não pode abrir sobre este template enquanto houver bloqueio.** O
próximo trabalho é transformar template **medido** em template **elegível** —
achar os dois acessores, por inspeção das assemblies do ScriptEngine e, se não
bastar, por reconhecimento read-only próprio.

Os dois textos canônicos, **medidos** e não supostos:

```text
GVL      {attribute 'qualified_only'} + VAR_GLOBAL/END_VAR   <- preservar o pragma
PROGRAM  PROGRAM <nome> + VAR/END_VAR, implementacao vazia   <- sem pragma
```

O `replace` substitui o documento **inteiro** preservando cada envelope.
Escrever `VAR_GLOBAL … END_VAR` na GVL apagaria o pragma; inserir um segundo
bloco aninharia. Nada disso seria detectável antes do build.

## Histórico: W1.2 como foi planejado

Parte **de novo do projeto-base sintético**, nunca de `W1-A1.project`: reusar a
saída de W1.1 misturaria a prova de criação de GVL com a de criação de POU, e o
ponto da subdivisão é justamente mantê-las separadas.

Sequência: contrato próprio → descoberta read-only do texto canônico de
declaração e implementação vazias → abertura isolada da fase
`W1_2_CREATE_PROGRAM` → probe novo → preflight → mutação em cópia nova →
reabertura independente → diff de exatamente um `PROGRAM` ST.

Allowlist futura dessa fase: `create_program` (ou a sobrecarga tipada que a
interface real exigir) e `save_as`. **Ainda sem escrever declaração ou
implementação** — a prova de criação fica separada da prova de edição textual.

---

**Histórico: o plano W1**, escrito e aprovado separadamente. Só depois
dele, e por decisão humana explícita, o gate muda — em **commit próprio,
isolado**, que não carrega implementação junto (`docs/28` §14).

O primeiro probe de escrita **foi autorizado, executado e encerrado** — é a
`W1.1` descrita acima, limitada a criar GVL vazia e salvar como projeto novo.
As etapas seguintes (POU ST vazia em W1.2, conteúdo mínimo em W1.3, compilação
offline em W1.4) continuam **não autorizadas**, cada uma exigindo o seu próprio
commit isolado de fase. Nada de Ladder, hardware, dispositivos, bibliotecas ou
tasks em nenhuma delas.

Conteúdo mínimo pretendido:

```iecst
VAR_GLOBAL
    g_xTesteCriacao : BOOL;
END_VAR
```

```iecst
PROGRAM PRG_TesteCriacao
VAR
    xLocal : BOOL;
END_VAR

xLocal := g_xTesteCriacao;
```

## O gate que a trilha de escrita vai encontrar

`scripts/mastertool/common/safety.py` declara `READ_ONLY_PHASE = True` e
bloqueia, fail-closed, exatamente as operações desta trilha:

```text
save_project  import_object  create_object  delete_object
modify_object  set_declaration  set_implementation
```

E há operações **permanentemente** proibidas, que a nova trilha não toca em
nenhum marco: `modify_original_project`, `apply_ai_changes_to_official_project`,
`change_hardware_configuration`, tudo de online/download/force.

Nenhum probe de escrita roda enquanto esse gate estiver fechado, e abri-lo é
uma decisão própria — parte do contrato `docs/27`, com autorização humana
explícita, nunca efeito colateral de um slice de implementação.

## Regras que não mudam

- **Nada é escrito em projeto industrial antes do gate transacional (W3).**
  Toda mutação de W1 e W2 ocorre em projeto novo e descartável.
- **Nenhum script roda dentro do MasterTool sem o usuário.** Lançar processo
  GUI contra arquivos reais exige supervisão visual humana — não é cadência,
  é limite estrutural.
- **UI visível** em toda execução real; diálogo inesperado → cancelar e
  registrar.
- **Nunca inventar API**: só o que está em
  `docs/api/mastertool-api-observations.md` ou observado em runtime.
- **`v0.1.0` é imutável.**
- **Dado de cliente não entra no repositório** — XML real, árvore de projeto
  real e inventário de dispositivo ficam fora; fixtures públicas são sintéticas
  e sanitizadas, com teste que falha se um identificador real aparecer.
- **Resultado científico inconclusivo ≠ falha operacional.**
- **Ausência de observação ≠ ausência de suporte** (`not_observed` nunca vira
  `unsupported`).
- Sem commit automático fora da disciplina estabelecida; sem push, PR, merge
  ou tag sem pedido explícito.

## Publicação

**Push é proibido por arquitetura nesta árvore.** Não adicionar remote aqui. A
publicação ocorre só no repo sanitizado, por fluxo separado: portar mudanças →
remover identificadores → revisar diff → testar lá → publicar dali. As tags
privadas permanecem locais.

## Ritmo acordado

```text
rapido   em engenharia offline e repetivel
moderado em novas integracoes
lento    em primeiras chamadas de API e escrita no projeto
```

A trilha de escrita é **a mais lenta das três** por definição: cada primeira
invocação de método mutável é uma primeira chamada de API *e* uma escrita.

Ordem de fechamento de slice:

```text
1. contrato documental
2. validacao do slice documental
3. commit documental          <- a especificacao entra no historico ANTES do codigo
4. implementacao
5. gate completo: testes, suite, validacao
6. atualizacao definitiva deste documento
7. atualizacao das memorias
8. commit da implementacao e do fechamento
9. push ou tag — somente quando explicitamente autorizado
```

Duas razões para a ordem, e nenhuma é cerimônia. O **commit documental vem antes
da implementação** para que o histórico prove que a especificação existia
primeiro: um contrato commitado junto do código que ele deveria reger é
indistinguível de racionalização escrita depois. E as **memórias vêm por
último**, para não criarem um segundo estado intermediário que envelhece antes
do slice terminar.

## Backlog

Não descartado — despriorizado, com contrato válido e pronto para retomada:

| Item | Onde está especificado |
|---|---|
| Semântica simbólica Ladder (L5) | `docs/21-contrato-semantica-ladder.md`, íntegro |
| Unificação ST + Ladder (L6) | `docs/14` §L6 |
| Validação real Ladder (L7) | `docs/14` §L7 |
| `pytest-asyncio` / `ruff` no venv | decisão explícita de não instalar por iniciativa própria |

## Defeitos das rodadas anteriores (todos corrigidos)

Registro honesto — a maioria foi introduzida por nós e pega por verificação
adversarial ou por execução real, não por revisão de código:

| Commit | Defeito |
|---|---|
| `1140784` | taxonomia confundia acesso por nome com enumeração; `dir()` vazio virava "evidência de ausência" |
| `d418885` | seção `runtime` nunca emitida — **toda** run supervisionada terminava `failed` desde a Etapa B |
| `1b650c3` | host pré-criava `export-root` dentro de `output/`, colidindo com a guarda de "output vazio" |
| `a294edc` | análise offline lia `export_xml_called` do arquivo errado e pulava sempre |
| `f130e5b` | hashes da fixture `sample_export` calculados sobre working tree híbrido LF/CRLF |
| `b190d1b` | `validate-repository.py` exigia `workspace/exports` e `workspace/logs` nunca versionados |

Os dois últimos só apareceram no **clone limpo**, invisíveis na máquina de
origem. Clonar exige `-c core.longpaths=true`: há caminhos de fixture que
estouram o MAX_PATH do Windows.

Três defeitos adicionais no mapeador de estrutura foram expostos pela
**fixture sintética** durante a construção (limiar de componente, arestas de
`ParallelBranch` ausentes, comparação injusta contra marcador vazio) — e só
apareceram porque o arquivo real e a fixture foram comparados entre si.

Da trilha de dispositivos, dois defeitos nossos pegos antes de qualquer
entrega: `<Value>` com filhos (984 de 1894 parâmetros) sendo classificado como
vazio, e `ParameterId` sozinho promovendo `Supported Functions` a `ip_address`
e `Dummy Parameter` a `subnet_mask` — daí a exigência de corroboração pelo nome
esperado e pela forma do valor.

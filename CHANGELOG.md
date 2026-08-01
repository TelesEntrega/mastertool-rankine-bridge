# Changelog

Formato baseado em [Keep a Changelog](https://keepachangelog.com/pt-BR/1.1.0/).

## [Unreleased]

### Alterado
- **Projeto-base trocado em 2026-07-31**: o usuário acrescentou **cartões de
  I/O** e determinou que o `TemplateExemplo v1.project`
  (`596625796e4efd54d3cc2d6286e858b683f0f58de66ab9a36eed532dd1d815f5`,
  **503.040 bytes**, contra 287.152 da base anterior) passa a ser a base. A
  classificação "projeto sintético mínimo com controlador NX3008" é aposentada
  em favor de **"projeto sintético com controlador NX3008 e cartões de I/O
  configurados"** — chamar de mínimo um projeto com I/O descreveria errado a
  superfície do diff, exatamente o erro que a classificação anterior existia
  para evitar. **Toda a baseline estrutural da base anterior fica invalidada**:
  3 raízes, 34 nós, `structure_sha256 b2825550…`, `node_path root/1/0/0` e o
  `type_guid` do `Application`. O `node_path` é o mais crítico, porque é caminho
  de **índices**: cartões de I/O mudam a árvore sob o `Device`, e um índice
  deslocado faz `root/1/0/0` deixar de apontar para o `Application` — o
  preflight abortaria com `container_not_found`, comportamento certo por motivo
  evitável. Antes de qualquer execução nova, varredura read-only com
  `probes/21` e recongelamento dos números. **Nada disso invalida W1.1 e W1.2**,
  que provaram capacidades e não propriedades de um arquivo; nem
  `W1-A1.project` e `W1-A2.project`, que seguem válidos como fixtures de W1.3
  por serem saídas congeladas e autocontidas — fica registrado, sem esconder,
  que a procedência delas é a base anterior, sem I/O. **W1.4 é o marco
  afetado**, por partir do projeto-base. Slice documental: nenhum código,
  probe, teste, gate ou execução.

### Adicionado
- **`docs/37`: W1.4 EXECUTADA E APROVADA — W1 ESTÁ COMPLETO.** A cadeia
  `create_gvl → create_program → replace ×3 → save_as → reabrir → build`
  rodou de ponta a ponta sobre o **projeto-base real do cliente**
  (`TemplateExemplo v1.project`, com cartões de I/O), com `integration_verified`:
  **0 erros e 0 avisos** de compilação, árvore 42 → 44 nós, adicionados
  exatamente `GVL_AI_TESTE` e `PRG_AI_TESTE`, `unexpected_additions: []`,
  `missing: []`, e o **output não alterado pelo build** (SHA-256 idêntico
  antes e depois). **O sistema cria, preenche, persiste e compila um projeto
  lógico em ST no MasterTool X.**
- **A fonte das mensagens de compilação foi encontrada, e a lacuna era do
  catálogo.** O stub do próprio `build()` diz onde procurar:
  `System.get_messages` / `System.get_message_objects`
  (`ScriptApplication.pyi` L41-49). **Iterar as categorias é essencial** — o
  default é a categoria `ScriptMessage`, onde o próprio script escreve; as
  mensagens de compilação vivem em outra, e o default devolveria vazio, que
  leria como "build sem erro". Dois `TypeError` medidos no caminho, da mesma
  família do que reprovou a `run-005`: `expected str, got Guid` (conversão
  explícita antes da chamada) e `expected Severity, got long` (parâmetro
  **omitido**, porque o default do produto já é "todas as severidades").
- **`system.exit(0)` encerra o MasterTool pelo próprio produto.**
  `CloseMainWindow()` não fecha quando há diálogo modal de salvar — e compilar
  **sempre** deixa o projeto alterado em memória, então o operador teve de
  clicar "Não" três vezes seguidas enquanto eu relançava sem corrigir a causa.
  Medido: **22,7 s** contra 71–133 s, sem clique manual. Não é `Stop-Process`
  disfarçado: é API documentada, chamada **depois** de os artefatos estarem no
  disco.

### Corrigido
- **A tabela de severidade estava incompleta, e a reprovação estava certa.**
  Com as mensagens lidas, a `run-019` classificou as oito como `unclassified`
  e reprovou — inclusive `Compile complete -- 0 errors, 0 warnings`. Faltava
  `Text`, o quinto membro do enum. Severidade desconhecida **não pode** virar
  aviso por conveniência, senão um erro desconhecido passaria por aprovado: o
  defeito era a tabela, não a regra.

### Adicionado
- **`probes/39` + `run_measure_iec_birth.ps1`: instrumento de MEDIÇÃO dos
  textos de nascimento** de `FUNCTION_BLOCK` e `FUNCTION`. O desenho resolve o
  paradoxo de que medir texto de nascimento **exige criar o objeto**: cria numa
  cópia descartável, lê os documentos e **não salva** — não há `save_as`,
  `save` nem `build` no probe, e o descarte é fechar a janela. **Mede sem
  persistir.** Uma sessão cobre as duas famílias porque vivem no mesmo
  container. O probe **não contém** texto de nascimento esperado para FB e
  FUNCTION — ele existe para descobri-los, e uma constante com o texto seria
  inventar o que se pretende medir; contém, como **controle**, os três hashes
  já medidos de GVL e PROGRAM: se a medição desses divergir, o instrumento está
  errado, não o MasterTool. Declara `W1_5_MEASURE_IEC_BIRTH`, que não existe —
  falha fechado hoje, por construção.
- **DUT continua bloqueado, e por falta de catálogo**: os valores do enum
  `DutType` não estão em `docs/27` nem em `docs/api/*`. Descobri-los exigiria
  reflexão .NET, **proibida dentro de probe de produção** — a lacuna fica
  registrada com proposta de medição em slice próprio, em vez de contornada.
  `create_dut` nunca é chamado.
- **Instrumentação de W1.4 — autoria integrada com `build`**: `probes/37`
  (preflight e postsave, read-only), `probes/38` (as **seis** mutações),
  `probes/40` (o `build`, em abertura separada) e
  `scripts/mastertool/run_w1_4_integrated.ps1`. **Nenhuma fase foi aberta** —
  os probes esperam `W1_4_INTEGRATED_BUILD`, que não existe em
  `PHASE_ALLOWED_OPERATIONS`, e por isso falham fechado hoje. Verificado por
  AST **independente dos testes da frente**: probe 37 com **zero** mutadores de
  proxy; probe 38 com exatamente `create_gvl`, `create_program`, **três**
  `replace` e **um** `save_as`; probe 40 com exatamente **um** `build` — todos
  com `assert_controlled_write_allowed` e o literal certo na linha
  imediatamente anterior. O wrapper ganhou `-TemplateQualification`
  **obrigatório**: lê o artefato do probe 35 e **recusa** quando
  `authoring_eligible` não é `true`, listando os bloqueios; **campo ausente
  também recusa**, porque ausência de resposta não é "sim".
- **`probes/36` + `run_probe_project_settings.ps1`: a compiler version foi
  MEDIDA em runtime** — `3.5.18.50`, pela cadeia literal
  `projects.primary.project_settings.get_compilerversion()`. Isso remove
  `compiler_version_unresolved`, um dos dois bloqueadores de elegibilidade.
  **A lacuna era do catálogo, não da API**: `docs/27` mediu 15 tipos-semente
  com raiz no MT8500 3.63 e `IScriptProject11` não estava entre eles. Achado
  que vale além deste slice: **o produto versiona stubs `.pyi`** em
  `MT9000\ScriptLib\Stubs\scriptengine\`, fonte de API oficial nunca usada
  aqui. Smoke read-only em `run-012`: três passos da cadeia ok, cópia e
  original intactos, zero mutadores, zero diálogos.

- **`docs/36-qualificacao-template-template-exemplo-v1.md`: o `TemplateExemplo v1.project` foi
  QUALIFICADO e NÃO é ELEGÍVEL para autoria.** Duas sessões read-only
  (`run-010`, `run-011`) sobre cópia descartável; original nunca aberto e com
  sha idêntico antes e depois. Medido: 3 raízes, **42 nós**, `Application` em
  `root/1/0/0` com match único, `MainTask`, nenhum conflito com
  `GVL_AI_TESTE`/`PRG_AI_TESTE`, zero mutadores, zero diálogos, zero órfãos.
  **`root/1/0/0` continuar valendo apesar dos cartões de I/O é resultado, não
  confirmação de suposição** — presumir teria acertado *por sorte*; o probe
  resolve o container por busca (nome + `type_guid`) e reporta o que achou.
  **Dois bloqueadores impedem a elegibilidade**: `compiler_version_unresolved`
  (falta o acessor de `IScriptProjectSettings2`, não o método) e
  `libraries_unresolved` (o nó Library Manager é alcançado e devolve **zero
  filhos** num projeto industrial — implausível como medição, logo é lacuna).
  W1.4 não pode abrir sobre este template enquanto houver bloqueio.

- **`docs/35-contrato-pacote-iec-minimo.md`**: contrato normativo de
  `FUNCTION_BLOCK`, `FUNCTION`, DUT `STRUCT` e DUT `ENUM`. Documento apenas;
  nenhuma fase aberta. **O valor dele está no que ele se recusa a afirmar**:
  registra **dez lacunas como "a medir"** em vez de preenchê-las por analogia
  — os textos de nascimento das quatro famílias, os valores do enum `DutType`,
  o `type_guid` de DUT e se ele distingue `STRUCT` de `ENUM`, o comportamento
  de `build()` sobre FB/FUNCTION, e a existência de um campo legível que
  distinga subtipos de POU. Esta última foi procurada e **não encontrada**, o
  que o documento registra como "não encontrado", nunca como "impossível". A
  consequência prática: **o pacote IEC começa por medição, não por
  implementação** — o precedente medido (GVL nasce com pragma e **sem** quebra
  final; declaração de PROGRAM nasce **com** quebra final; implementação nasce
  **vazia**) mostra que o texto de nascimento diverge de família para família
  no detalhe que mais engana, e preenchê-lo por analogia seria inventar.
  Incorpora os dois fatos medidos em W1.3B: a linguagem **não** serve como
  discriminador verificável, e critérios do tipo "nenhum outro objeto da
  família X foi alterado" precisam citar `probes/21`, não `get_children(False)`.

- **`src/mastertool_bridge/planner/`: planner declarativo** — `project_spec` →
  validação → grafo de dependências → ordenação topológica → plano literal de
  autoria → expected diff → manifest. **O planner produz dados; o executor tem
  chamadas literais** — por isso `operation` é um conjunto **fechado** de doze
  valores, provado por seis ângulos, incluindo AST: todo `operation=` é um
  `ast.Name` com id `OPERATION_*`, nunca literal solto, f-string ou
  concatenação, o que torna **impossível** fabricar nome de operação a partir
  de dado. Empate na topológica resolvido por `(rank da família, nome)`, com
  nomes IEC em ASCII puro — a comparação não depende de locale nem de versão
  de Python, e o plano fica **invariante a permutação** das listas da spec.
  Determinismo verificado em **processos separados** com `PYTHONHASHSEED`
  variado: repetir no mesmo processo não prova nada, porque ali o hash de
  string é fixo. **`create_program_call` não tem API catalogada** e por isso
  mapeia para `None` no `EXECUTOR_CONTRACT`, vira lacuna de medição e deixa o
  plano `executable: false` — fail-closed verificado por comportamento na
  integração, e não pelo relato. `expected_before_sha256` de todo `replace` é
  `null`, com `created_by_sequence` apontando o passo de criação: o texto de
  esqueleto pós-`create_*` **não foi medido** para DUT/FUNCTION/FB/PROGRAM, e
  declarar hash inventado ali seria pior que declarar `null`.

### Corrigido
- **Teste de determinismo do planner acusava não-determinismo onde havia erro
  de codificação.** `subprocess.run(text=True)` decodifica a saída do
  subprocesso com o code page do console (cp1252 nesta máquina), e o plano
  voltava com `nÃ£o` no lugar de `não`; os cinco subprocessos **concordavam
  entre si**, e só a comparação com o plano gerado em processo é que quebrava.
  Mesma classe do BOM em `session-verdict.json` — suposição de codificação no
  Windows. Corrigido nos **dois** lados: o filho passou a escrever bytes UTF-8
  explícitos (`sys.stdout.buffer.write`) em vez de deixar a codificação a cargo
  do default do interpretador, e o leitor decodifica UTF-8 explícito. Assim
  produtor e consumidor concordam **por construção**, e não por coincidência de
  ambiente. Achado na integração serial: a frente havia reportado o teste como
  verde, medido enquanto outras frentes escreviam na mesma árvore — **um verde
  medido em árvore instável não é verde**.

- **`src/mastertool_bridge/templates/`: registry de templates** — schema e
  validador offline determinístico. A decisão que decide o desenho:
  **`node_path` é amarrado ao `sha256` do arquivo, nunca ao `template_id`**.
  Um node_path é caminho de índices, válido para **um arquivo**, não para "o
  template"; duas versões do mesmo `template_id` são entradas independentes,
  cada uma com o seu node_path. A única API pública para obter node_path é
  `resolve_node_path_for_file(result, file_sha256)`, que só devolve valor com
  o hash exato — **não existe** `resolve_node_path_by_template_id`, e há teste
  exigindo que não passe a existir. Duas entradas com o mesmo `sha256` e dados
  divergentes são contradição e reprovam a validação inteira. `allow_download`
  é recusado quando `true`, com a razão na mensagem: `download_missing_libraries`
  faz rede e é API proibida por contrato. Entrada degenerada (`None`, `[]`,
  `str`, `int`, `bool`, `{}`) devolve problemas e **nunca levanta** — verificado
  por comportamento na integração, não pelo relato.

### Pendente
- **O instrumento de qualificação e o registry ainda NÃO compõem.** O probe 35
  emite `compiler_version: None` porque nenhum acessor de
  `IScriptProjectSettings2` está catalogado; o registry **exige**
  `compiler_version` como string não vazia. Cada lado está correto isolado — o
  probe se recusa a inventar API, o registry se recusa a aceitar template
  incompleto — mas a saída de um não entra no outro. Descoberto na integração
  serial, ao montar um registry sintético e ver a recusa. **Nenhum dos dois foi
  enfraquecido para fazer a junção passar.** Resolver exige escolher: ou
  reconhecimento read-only que ache o acessor de compiler version, ou modelar
  o campo explicitamente como "medido ou lacuna". É decisão de modelagem, e
  fica registrada em vez de decidida de ofício.

- **Instrumento de qualificação read-only de template**:
  `probes/35_qualify_template_readonly.py` e
  `scripts/mastertool/run_tmf_v1_qualification.ps1`. É a **precondição de
  W1.4**: `node_path` é caminho de **índices**, e os cartões de I/O do
  `TemplateExemplo v1.project` deslocam índices — `root/1/0/0` foi confirmado para a
  linhagem da base **anterior**, não para a nova. O probe **não** recebe
  node_path pronto: resolve o `Application` por busca (nome + `type_guid`) e
  **reporta** o que encontrou. Reaproveita `ReadOnlyProjectScanner` em vez de
  escrever um segundo caminhador de árvore — a varredura recursiva com limite
  de profundidade e de nós já existia em `probes/21`, e o probe 35 é um
  **classificador de segunda passagem sobre a mesma saída**. Acrescenta o que
  faltava: classificação de `type_guid` conhecidos contra `unclassified`,
  detecção de **conflito de nome** com `GVL_AI_TESTE`/`PRG_AI_TESTE` (se já
  existirem, W1.4 não pode rodar), derivação de `libraries`/`tasks` a partir
  dos filhos de "Library Manager"/"Task Configuration", `persistent_tree_sha256`
  e o candidato de registry do template. Zero mutadores — verificado por
  **receptor** na AST, independentemente dos testes do próprio probe: todo
  `.append` é lista Python e o único `.insert` é `sys.path`. Wrapper
  fail-closed, ASCII puro, 0 erros de parse, nunca `--noUI`, nunca
  `Stop-Process`. **Ainda não executado** — nenhuma janela foi aberta.
- **`docs/34-execucao-w1-3b-edicao-program.md`: W1.3B EXECUTADA E APROVADA**
  (`run-009`). Os **dois** documentos textuais de um `PROGRAM` — declaração e
  implementação — foram substituídos na mesma sessão por `replace`, persistidos
  por um **único** `save_as`, e recuperados idênticos em reabertura
  independente. Isso fecha a lacuna que W1.3A não podia fechar: lá havia um
  documento, e o estado "um gravado e o outro não" era logicamente impossível;
  aqui era possível e **não ocorreu**. Entrada `W1-A2.project`
  (`67092e58…a1e2a1`) intacta byte a byte; saída `W1-A4.project` (288.656 bytes,
  `b220611e…a2076176`); declaração `6a2401fa…435841` → `6e4b13ab…dfa80f5`;
  implementação `e3b0c442…7852b855` (a string vazia) → `313cdb1f…1347d517`;
  **duas** substituições e **um** `save_as` no journal; árvore com 9 filhos
  antes e depois, conferida por **segunda leitura independente** dos arquivos
  de varredura crus — um diff calculado pelo mesmo código que fez a mutação é
  testemunha de si mesmo. Zero diálogos, zero órfãos, `session-verdict.json`
  **sem BOM** (primeira execução após `bc23d4b`, validando a correção em campo).
  **Com W1.1, W1.2, W1.3A e W1.3B encerrados, W1.3 está completo.**
- **Dois dos quinze critérios de W1.3B NÃO foram verificados — e estão
  nomeados, não escondidos.** (1) *"nenhum outro PROGRAM alterado"*: a
  varredura usa `get_children(False)`, **apenas filhos diretos**, então a
  comparação cobre o nível do `Application` e não os POUs dentro de `UserPOUs`/
  `SystemPOUs`; afirmar o critério como escrito exigiria varredura recursiva
  (`probes/21`). (2) *"linguagem continua ST"*: **não há API catalogada que
  leia a linguagem de um objeto existente** — `language` só aparece como
  parâmetro de **entrada** dos `create_*`, e `IScriptImplementationLanguages`
  só fornece GUIDs. Ler de volta exigiria API não catalogada, o que o contrato
  proíbe. O caminho certo é o **`build` de W1.4**: ST que compila é ST, e isso
  prova mais que um rótulo conferido.
- **`docs/33-execucao-w1-3a-edicao-gvl.md`: W1.3A EXECUTADA E APROVADA.**
  `replace` sobre `IScriptTextDocument` cria texto que sobrevive a `save_as` e
  a uma **reabertura independente** — a etapa de verificação abre
  `W1-A3.project` num processo novo, sem nenhum estado em memória herdado da
  mutação. Texto persistido conferido por SHA-256
  (`71f8079f…d261a017c`), árvore inalterada (9 filhos antes e depois, quatro
  listas de diff estrutural vazias), entrada intacta
  (`a0460e82…be0614` antes **e** depois — `save_as` escreve em arquivo novo),
  saída `W1-A3.project` (288.256 bytes, `f7d9d819…bc9847a1`), exatamente **um**
  `replace` e **um** `save_as` no journal, `no_other_mutator_requested: true`,
  zero diálogos e zero órfãos em três execuções. O código de saída do launcher
  foi `0` nas três e **não decidiu nada**: quem decide é o artefato de
  conclusão gravado pelo probe. **O que não está provado: que o texto
  compila** — `build` pertence a W1.4, e a separação é deliberada.
- `tests/unit/test_wrappers_artifact_encoding.py`: guarda de codificação dos
  artefatos dos wrappers, varrendo o diretório em vez de uma lista fixa (ver
  em **Corrigido**).

### Corrigido
- **`session-verdict.json` era gravado com BOM.** `Out-File -Encoding utf8`
  produz BOM no PowerShell 5.1, e ler o veredito de volta falhava com
  `Unexpected UTF-8 BOM` — o arquivo que existe para dar veredito da sessão não
  podia ser lido por leitor JSON estrito. Os **quatro** wrappers de W1 tinham a
  mesma linha; os quatro passaram a gravar por
  `[System.IO.File]::WriteAllText` com `UTF8Encoding($false)`. Achado na
  execução real de W1.3A. **2.220 testes passavam com o defeito no lugar**,
  porque nenhum olhava a *codificação* do que o wrapper grava, só o que ele
  decide — um artefato que o próprio pipeline não consegue ler é evidência que
  não pode ser consumida. O `session-verdict.json` de `run-008` **continua com
  BOM**: é registro histórico de execução feita com o código antigo, e
  reescrevê-lo falsificaria o registro.
- **A baseline de testes voltou a zero falhas** (`2215 passed, 1 skipped`).
  Os 7 testes `async` de `tests/test_mcp_server_e2e.py` falhavam porque
  **`pytest-asyncio` não estava declarado em manifesto nenhum**: existia por
  instalação manual em `C:\Program Files\Python311` e faltava na `.venv` do
  projeto. Declarado agora em `requirements-dev.txt`. **A lógica do servidor
  MCP não foi tocada** — sob o interpretador que tinha o plugin, os 7 já
  passavam, o que prova que não havia segunda causa funcional escondida.
  Nenhum `xfail`, `skip` novo ou exclusão de teste foi usado como correção.
- **Teto `mcp<2` em `pyproject.toml` e `requirements-dev.txt`.** Medido, não
  suposto: `mcp>=1.0` resolve hoje para **2.0.0**, que **removeu
  `mcp.server.fastmcp`** — o módulo importado em `mcp_server.py:185`. Provisionar
  a `.venv` a partir do manifesto antigo instalava a série 2, o subprocesso do
  servidor morria em `ModuleNotFoundError` e os mesmos 7 testes voltavam a
  falhar, agora por outro motivo. O manifesto anterior descrevia um ambiente
  que não funciona; migrar para a API 2.x é slice funcional próprio.
- `requirements-dev.txt` passou a listar `mcp`, que faltava: um ambiente
  montado só a partir dele importava o teste E2E e morria antes de coletar.

### Adicionado
- `tests/unit/test_test_infrastructure.py`: guarda para que a infraestrutura de
  teste não volte a mentir. Exige que **capacidade usada pelo repositório esteja
  declarada em manifesto do repositório**, e não apenas presente por acidente no
  ambiente de quem rodou — cada exigência é verificada em par, na **declaração**
  e na **execução**, porque declaração verde sobre ambiente vermelho foi
  exatamente o estado que passou despercebido. Cobre: existência de teste
  `async` na suíte (âncora que avisa quando a dependência virar obsoleta);
  `pytest-asyncio` declarado **e** carregado; `mcp` com teto `<2` nos **dois**
  manifestos **e** na versão instalada; `mcp_server.py` ainda usando a API
  FastMCP da série 1 (âncora que manda **levantar** o teto quando a migração
  vier, em vez de congelar o repo por inércia); e todo `async def test_` com
  `@pytest.mark.asyncio` explícito — em modo strict, o que não tem marcador é
  coletado e **nunca executado**, falha silenciosa que `asyncio_mode = auto`
  esconderia em vez de resolver. **Nenhuma configuração `pytest` foi
  adicionada**: os testes já usam marcador explícito, então o modo strict
  padrão é o correto.
- Instrumentação de **W1.3B — edição textual de PROGRAM ST**:
  `probes/33_verify_program_edit_w1_3b_readonly.py`,
  `probes/34_edit_program_w1_3b.py` e
  `scripts/mastertool/run_w1_3b_edit_program.ps1`. **Gate fechado**:
  `W1_3B_EDIT_PROGRAM` não existe em `PHASE_ALLOWED_OPERATIONS`. O que
  separa B de A é que um PROGRAM tem **dois** documentos de texto
  independentes — declaração e implementação — contra um da GVL: são **três**
  mutações por sessão em vez de duas, e existe um estado que W1.3A não
  consegue produzir, o de **um documento gravado e o outro não**. As
  canônicas divergem no detalhe que mais engana: a declaração nasce **com**
  quebra final (`6a2401fa…435841`) e a implementação nasce **vazia**
  (`e3b0c442…7852b855`, o sha da string vazia). Entrada: `W1-A2.project`
  (`67092e58…a1e2a1`, 288.208 bytes), saída aprovada de W1.2, somente
  leitura, copiada por run; nenhum PROGRAM é criado aqui. Verificação por
  AST: zero mutadores de proxy no probe 33; no probe 34, exatamente três —
  `declaration_document.replace`, `implementation_document.replace`,
  `project.save_as` — todas com a guarda na linha imediatamente anterior.
  **W1.3B fica preparado e bloqueado**: o próximo gate real é W1.3A e só
  ele, porque abrir os dois ao mesmo tempo deixaria duas fases mutáveis em
  aberto — exatamente o que o desenho de fase única existe para impedir.
- Instrumentação de **W1.3A — edição textual de GVL**:
  `probes/31_verify_gvl_edit_w1_3a_readonly.py` (preflight e postsave),
  `probes/32_edit_gvl_w1_3a.py` (a mutação) e
  `scripts/mastertool/run_w1_3a_edit_gvl.ps1` (wrapper supervisionado).
  **O gate continua fechado**: `READ_ONLY_PHASE = True`,
  `CONTROLLED_WRITE_PHASE = None` e a fase `W1_3A_EDIT_GVL` **não existe**
  em `PHASE_ALLOWED_OPERATIONS` — executar o probe 32 hoje aborta na
  guarda, antes de tocar arquivo. **W1.3A não cria nada**: a entrada é
  `W1-A1.project` (`a0460e82…be0614`, 287.824 bytes), saída aprovada de
  W1.1, tratada como fixture imutável e copiada para uma cópia descartável
  por run — assim `replace` é a **única capacidade variável** da sessão, e
  `save_as` entra como transporte já provado em W1.1. Verificação por AST
  independente dos testes: o probe 31 tem **zero** mutadores de proxy (todo
  `.append` é lista, todo `.insert` é `sys.path`) e o probe 32 tem
  exatamente duas mutações — `text_document.replace` e `project.save_as` —,
  cada uma com `assert_controlled_write_allowed` e o literal certo na linha
  **imediatamente** anterior. `insert` e `append` **permanecem no registro
  de mutadores conhecidos**: como colidem com `list.append` e
  `sys.path.insert`, a checagem é por **receptor**, não por nome de método
  — o documento de texto só pode receber `replace`.
- `docs/32-plano-w1-4-integracao-e-build.md`: contrato de **W1.4 — autoria
  integrada e build offline**, o marco que volta ao projeto-base e encadeia
  numa única sessão o que W1.1, W1.2 e W1.3 provam isoladamente:
  `create_gvl` → `create_program` → `replace` (GVL) → `replace` (declaração)
  → `replace` (implementação) → `save_as` → reabrir → `build` → verificar →
  diff estrutural. Documento apenas; **nenhuma fase é aberta** —
  `W1_4_INTEGRATED_AUTHORING`, `build`, criação combinada e referência
  cruzada ficam todas como plano futuro, e `CONTROLLED_WRITE_PHASE` continua
  `None`. **`build()` entra aqui e só aqui**: em W1.3 ele teria misturado
  "o texto persistiu" com "o texto compila", e um erro de compilação sobre
  texto corretamente persistido é achado sobre o **conteúdo**, não sobre a
  capacidade de escrever. A implementação integrada usa
  `xLocal := GVL_AI_TESTE.g_xTesteCriacao;` — o prefixo é obrigatório por
  causa do pragma `qualified_only` que a GVL carrega desde o nascimento,
  medido em W1.1; sem ele o build falharia por conteúdo. A tabela de *fault
  injection* cobre catorze pontos e ancora a regra de **nenhuma aprovação
  parcial automática** na razão certa: `create_*` devolve o objeto **já
  inserido** e não existe rollback transacional, logo a unidade descartada é
  sempre a **cópia inteira**, nunca uma operação isolada. Riscos do build
  registrados: resolução de biblioteca pode disparar rede e qualquer indício
  aborta; `download_missing_libraries` e `set_compilerversion_to_newest`
  seguem proibidos; **aviso não é erro** — o critério é "sem erro", com os
  avisos registrados na íntegra. Duas lacunas ficam **declaradas em vez de
  decididas**: a baseline estrutural da base nova (com cartões de I/O) ainda
  não foi medida (instrumento: `probes/21`), e o `type_guid` de POU não
  distingue `PROGRAM` de `FUNCTION_BLOCK`.
- `src/mastertool_bridge/spec/`: primeiro draft do **modelo declarativo
  `project_spec`** — JSON Schema (`project_spec.schema.json`) e validador
  offline determinístico (`validator.py`), sem planner executável, sem
  executor e sem dispatch de mutador. **A linguagem é sempre um GUID**: a
  string `"ST"` não é apenas rejeitada, é estruturalmente impossível, porque
  `language` é um objeto `{"guid": …}` — o parâmetro real da API é
  `Nullable<Guid>`, e texto ali inventaria uma API que não existe.
  `creation_order` usa chave qualificada por família (`duts:ST_Equipamento`) para
  que nomes iguais em famílias diferentes não colidam no identificador.
  `type_guid` foi **deliberadamente omitido**: é dado **medido** depois da
  criação, não algo que o autor declara. `schema_version` é inteiro,
  seguindo a convenção dos módulos CPython de `src/mastertool_bridge/` — e
  não a convenção de string `"1.0"` dos probes IronPython. Entrada
  degenerada (`None`, `[]`, `str`, `int`, `bool`) devolve problemas e
  **nunca levanta**.
- `scripts/mastertool/common/authoring_text.py`: primitivas determinísticas
  de verificação de autoria, compartilhadas pelos probes de W1.3 e W1.4 —
  normalização e equivalência textual (CRLF≡LF, espaço à direita por linha,
  **uma** quebra final), `sha256` de texto e de arquivo, relatório de diff,
  diferença de multiconjunto, identidade de objeto, diff estrutural,
  `Journal` com relógio injetado e construtores de manifesto e artefato de
  conclusão. Camada **pura**: importa apenas `hashlib`, não toca no
  ScriptEngine e não conhece o MasterTool — o que permite testá-la em CPython
  3 sem simular a IDE, embora ela seja executada sob IronPython 2.7.
- `docs/31-plano-w1-3-escrita-textual-controlada.md`: contrato de **W1.3 —
  escrita textual controlada**. Documento apenas; nenhuma fase aberta,
  `CONTROLLED_WRITE_PHASE` continua `None`. **Decisão de rota: W1.3 não recria
  objetos.** Os artefatos aprovados de W1.1 e W1.2 viram entradas imutáveis —
  `W1-A1.project` (`a0460e82…be0614`, 287.824 bytes) para editar a GVL e
  `W1-A2.project` (`67092e58…a1e2a1`, 288.208 bytes) para editar o PROGRAM —,
  ambos congelados como somente leitura, com cópia descartável nova por run.
  Recriar os objetos e editar o texto na mesma sessão misturaria quatro
  capacidades (`create_gvl`, `create_program`, `replace`, `save_as`) e uma
  falha depois da criação ficaria ambígua: identidade do objeto, acesso ao
  documento, conteúdo textual ou persistência. Com os artefatos como fixture,
  `IScriptTextDocument.replace` fica como **única variável sob teste**. Duas
  fases independentes, `W1_3A_EDIT_GVL` e `W1_3B_EDIT_PROGRAM`, com a mesma
  allowlist (`replace`, `save_as`) e alvos distintos — a restrição de alvo não
  vive no gate, que autoriza a operação, mas no probe, que carrega objeto e
  documento como literais; são camadas diferentes, e é por isso que duas fases
  com a mesma allowlist ainda são duas fases. `insert`, `append` e
  `replace_line` ficam proibidos **de propósito**, embora existam: `replace` do
  documento inteiro é a única forma cujo estado final não depende de offset e,
  portanto, a única verificável por hash. Ficam registrados os textos canônicos
  **medidos** e os finais planejados, com SHA-256 dos quatro, mais a assimetria
  que só a medição revela — **a GVL não termina em quebra de linha e o PROGRAM
  termina** —, e o registro de que `e3b0c442…b855` é o hash da string vazia, para
  que ninguém confunda "vazio medido" com "não foi possível ler". O journal
  distingue `replace_gvl_declaration`, `replace_program_declaration` e
  `replace_program_implementation`, embora a operação de segurança seja sempre o
  literal `replace`: sem isso, dois `replace` no journal de W1.3B seriam
  indistinguíveis. `build` **não** roda em W1.3 — fica em W1.4, porque um erro
  de compilação num texto corretamente persistido é achado sobre o conteúdo, não
  sobre a capacidade de escrever.

### Alterado
- **W1.2 encerrado e aprovado em 2026-07-31: o sistema cria GVL e cria POU no
  MasterTool X 4.1**, com persistência confirmada por reabertura independente
  nos dois casos. Projeto-base e cópia com `6183d01d…5540dd3` antes e depois;
  saída `W1-A2.project` com `67092e58…a1e2a1`; diff de exatamente **+1**
  objeto, `PRG_AI_TESTE`. Três runs, todas preservadas: **run-004** aprovou o
  preflight e mediu o **GUID da linguagem ST**
  (`cc393387-a21c-4f68-a3e3-84c36951965d`) no global `ImplementationLanguages`
  — **segundo** candidato da lista literal, não o primeiro, o que teria feito
  um único nome falhar; **run-005** reprovou com segurança; **run-006**
  executou `create_program` uma vez e `save_as` uma vez, terminando em
  `saved_as` mais `postsave_verified`. Nenhum diálogo, zero órfãos, `.opt`
  confinados, e as janelas fechadas pelo próprio host por `CloseMainWindow()`
  — nunca `Stop-Process`, que `docs/28` §7 proíbe.
- **O texto canônico de um `PROGRAM` recém-criado foi medido** depois de
  `create_program` e antes de `save_as`, como o plano exigia: `PROGRAM <nome>` +
  `VAR`/`END_VAR`, implementação vazia, SHA-256 `6a2401fa…435841`. Duas
  diferenças que só a medição revelaria — **não há pragma** (ao contrário da
  GVL, que nasce com `{attribute 'qualified_only'}`) e **não há comentário de
  cabeçalho** (o dos POUs do projeto-base vem do template Altus, não do objeto
  novo). Tratar o texto de um POU preexistente como canônico de um recém-criado
  teria produzido conteúdo errado em W1.3.
- Fase `W1_2_CREATE_PROGRAM` **encerrada** em commit isolado, como em W1.1.
  `READ_ONLY_PHASE` permanece `True` e nenhuma operação mutável fica
  autorizada; as entradas de W1.1 e W1.2 ficam no mapa como registro histórico.

### Corrigido
- **O GUID da linguagem não pode viajar como texto** (achado da `run-005`).
  `create_program` recusa string com `TypeError: expected Nullable[Guid], got
  str`: o plano só transporta texto — JSON não tem tipo `Guid` — e o IronPython
  não converte sozinho. A falha ocorreu **antes** de tocar o projeto: nenhuma
  mutação, nenhum arquivo criado, e a cópia marcada para descarte pela política,
  que não presume "nada aconteceu" só porque a exceção pareceu precoce. A
  conversão passou para a fase de precondição, via `System.Guid` — tipo do .NET
  base, não API do MasterTool —, nunca entre a guarda e a chamada; falha de
  conversão é `precondition_failed`, não `create_program_failed`, porque uma
  nem chegou a pedir autorização.
- **Artefato que se contradizia** (achado da `run-006`): o `completion` de um
  postsave **aprovado** declarava `is_success: False` ao lado de
  `status: postsave_verified`, porque o campo comparava só com
  `preflight_passed` e o modo postsave tem estado de sucesso próprio. O
  veredito da sessão não dependia dele, mas a evidência arquivada sim — e é ela
  que sobrevive à sessão. Um artefato que se contradiz é pior que um omisso:
  quem lê acredita no campo errado.

### Adicionado
- `docs/30-plano-w1-2-criacao-program-st.md` e
  `probes/29_preflight_program_w1_2_readonly.py`: contrato e instrumento de
  reconhecimento de **W1.2 — criar um `PROGRAM` ST vazio**. Nenhuma fase foi
  aberta e nenhuma operação mutável está autorizada;
  `CONTROLLED_WRITE_PHASE` continua `None`. **Correção conceitual incorporada:
  o texto padrão de um `PROGRAM` recém-criado não é descobrível antes da
  criação** — o preflight prova a API, o GUID de ST, a identidade estrutural
  dos PROGRAMs existentes e a interface textual, e o conteúdo padrão do objeto
  novo só será medido depois de `create_program` e antes de `save_as`, como foi
  com a GVL em W1.1. Ler a declaração de um PROGRAM preexistente é evidência
  **auxiliar**, e o artefato carrega essa ressalva num campo próprio, com teste
  que falha se ela sumir: a ressalva no artefato vale mais que a no documento,
  porque é ela que acompanha a evidência quando alguém a reler daqui a um ano.
  O GUID de ST não é hardcodado nem substituído pela string `"ST"` — o
  parâmetro é `Nullable<Guid>`; como **nenhum membro dos assemblies devolve
  `IScriptImplementationLanguages`**, ele só pode vir de um global injetado
  cujo nome não está catalogado, então o probe tenta uma lista literal e
  fechada de candidatos e, falhando, devolve `st_language_guid_missing`
  **junto com os nomes dos globais efetivamente injetados** — pista para o
  próximo slice em vez de beco sem saída. `online` e `device_repository` ficam
  fora dos candidatos porque podem iniciar comunicação só de serem lidos.
  `create_pou` fica **proibida** em W1.2 se `create_program` bastar, e nunca
  como fallback na mesma sessão: tentar a segunda quando a primeira falha
  transforma prova em tentativa e erro. Registrado o trap medido no
  projeto-base — `MainPrg` aparece **duas vezes**, como POU e como referência
  de chamada sob a task, com `type_guid` diferente —, mais a limitação de que o
  `type_guid` de POU não distingue `PROGRAM` de `FUNCTION_BLOCK`, declarada
  como lacuna em vez de resolvida por discriminador inventado. Onze estados
  fechados, só `preflight_passed` com código zero. 61 testes com dublês
  estritos e verificação AST, entre eles um que percorre a AST exigindo
  **identificadores ASCII** — Python 2 recusa identificador não-ASCII e o
  `py_compile` do CPython 3 não acusaria; ele pegou um deslize real durante a
  escrita do probe.

### Alterado
- **W1.1 encerrado e aprovado em 2026-07-31.** A primeira escrita controlada no
  MasterTool X aconteceu e a persistência está provada por reabertura
  independente — deixa de ser prova de API e passa a ser capacidade operacional
  auditada. `HEAD` da sessão `8e7813d`; projeto-base e cópia de trabalho com
  `6183d01d…5540dd3` **antes e depois** (o `save_as` gravou em arquivo novo e
  `save()` nunca foi chamado); saída `W1-A1.project` com `a0460e82…be0614`;
  diff de exatamente **+1** objeto persistente, `GVL_AI_TESTE`, sem nenhuma
  alteração inesperada. Três runs, todas preservadas: **run-001** reprovou o
  preflight **com segurança** (o probe lia `type_guid` do objeto em vez de
  `object.type`) sem nenhuma mutação e com hash intacto — é a única evidência
  de reprovação segura que a trilha produziu, e por isso não é lixo;
  **run-002** aprovou o preflight e provou que **o `Application` expõe
  `create_gvl` diretamente**, `callable`, sem `Extender`, cast ou reflexão;
  **run-003** executou `create_gvl` uma vez e `save_as` uma vez, sem nenhum
  outro mutador solicitado, terminando em `saved_as` mais `postsave_verified`.
  Nas três: nenhum diálogo, zero processos órfãos, `.opt` confinados ao
  diretório da sessão, e o `exit code` do launcher sempre **vazio** — o
  veredito saiu inteiramente dos artefatos de conclusão, como projetado.
- **O texto canônico de uma GVL vazia foi medido**, e ele contradiz o que o
  plano supunha. O documento gerado pelo próprio MasterTool é
  `{attribute 'qualified_only'}` + `VAR_GLOBAL` + `END_VAR` (SHA-256 textual
  `fd27fd81…310affb`, 3 linhas): ele carrega o **bloco completo**, não só o
  corpo interno, e traz um **pragma que ninguém pediu**. Substituir apenas por
  `VAR_GLOBAL … END_VAR` apagaria o pragma; inserir outro `VAR_GLOBAL` dentro
  do documento aninharia o bloco — e qualquer uma das duas falharia no build,
  longe da causa. `docs/29` corrige o conteúdo de W1.3 para preservar o
  envelope canônico inteiro, e passa a exigir que a comparação pós-save
  confirme pragma preservado, exatamente um bloco `VAR_GLOBAL`, exatamente uma
  declaração, e nenhuma alteração em outra GVL. A pergunta foi respondida
  **por leitura, sem escrever nada** — exatamente o que o plano mandava.
- **Identidade de GVL deixa de ser heurística.** O `type_guid` medido em
  runtime, `ffbfa93a-b94d-45fc-a329-229860183b1d`, é o mesmo das GVLs
  preexistentes do projeto-base, o que o torna verificável contra a própria
  baseline. O critério principal passa a ser o GUID mais nome, `is_folder`,
  `is_transient` e `has_textual_declaration`; a forma estrutural anterior
  (`has_textual_declaration and not is_folder`) fica registrada como **fallback
  conservador**, evidência auxiliar e nunca identidade definitiva.
- `docs/29` troca a exigência de "projeto vazio" pela baseline aprovada:
  **projeto sintético mínimo com controlador NX3008**. A medição mostrou que o
  base do ensaio é um esqueleto Altus — Device NX3008 com COM/NET/CAN, mais
  `SystemPOUs`, `UserPOUs`, `UserGVLs` e `SystemGVLs` padrão — e chamá-lo de
  vazio descreveria errado a superfície do diff. Ele é aceitável porque foi
  criado para o ensaio, não tem lógica nem dado de cliente, não tem escravo de
  fieldbus, tem um `Application` real e é usado somente por cópia descartável;
  criar um projeto de fato vazio exigiria `ScriptProjects.create`, e ampliar a
  allowlist para preparar um ensaio inverteria a ordem entre autorização e uso.
  Os POUs e GVLs padrão passam a ser **baseline imutável**: qualquer alteração
  ou desaparecimento deles reprova a sessão. A baseline fica congelada por
  SHA-256 do arquivo, 3 raízes, 34 nós, `node_path` `root/1/0/0`, nome
  `Application`, `type_guid` esperado e um **hash determinístico da estrutura**
  sobre `node_id | name | type_guid` — com `object_guid` deliberadamente fora,
  porque ele não é estável entre sessões (`docs/22`) e faria o hash mudar sem
  que o projeto mudasse. Quem faz cumprir a baseline antes do preflight é o
  SHA-256 do arquivo; as contagens são o congelamento legível, não um segundo
  mecanismo. O expected diff continua sendo exatamente `+ GVL_AI_TESTE`.
  Nenhum caminho local nem dado operacional da máquina foi versionado.

### Corrigido
- **Falha de cobertura do gate de segurança**, encontrada em 2026-07-31 ao
  preparar a autorização de W1.1 — **por teste, sem nenhuma invocação de API do
  MasterTool e sem nenhuma mutação executada**. `assert_operation_allowed()`
  conhecia apenas os sete nomes legados (`save_project`, `import_object`,
  `create_object`, `delete_object`, `modify_object`, `set_declaration`,
  `set_implementation`) e **devolvia permissão para qualquer outro nome**. Os
  nomes reais das APIs do MasterTool X nunca tinham sido registrados, de modo
  que, com `READ_ONLY_PHASE = True`, passavam `create_gvl`, `save_as`,
  `create_program`, `replace`, `build` e `import_xml` — a superfície inteira da
  trilha de escrita. O gate protegia o vocabulário antigo e ignorava o novo: a
  falha não era de política, era de **cobertura**, e o modo "somente leitura"
  nunca chegou a cobrir o que `docs/28` e `docs/29` afirmavam que ele cobria.
  Corrigido em `b8ad7bb` com registro literal de **40 operações mutáveis**
  catalogadas (`docs/27` §7), **fail-closed** para nome desconhecido, parcial,
  com curinga ou fora de tipo, autorização por **fase nomeada** com allowlist
  literal, **uma única porta de decisão** (a guarda legada desvia toda operação
  mutável do MasterTool X, inclusive as autorizadas) e 79 testes estruturais
  cobrindo nomes exatos e entradas adversariais.

### Alterado
- `docs/28` e `docs/29` alinhados ao gate real. A especificação exigia
  "decisão humana explícita de **mudar `READ_ONLY_PHASE`**" — requisito agora
  **removido**, porque trocar esse booleano para `False` autorizaria de uma vez
  as sete operações legadas, que é exatamente a abertura genérica que o
  contrato existe para impedir. O modelo normativo passa a ser: `READ_ONLY_PHASE`
  permanece `True` **sempre**; toda operação mutável conhecida pertence ao
  registro literal; toda operação mutável passa por uma única porta; uma fase
  **nomeada** autoriza uma allowlist literal mínima; W1.1 autoriza somente
  `create_gvl` e `save_as`; desconhecido, fase desconhecida ou configuração
  incompleta falham fechados; e não existe autorização por prefixo, padrão,
  curinga ou correspondência parcial. `docs/28` §14 passa a exigir sete passos,
  entre eles os **testes estruturais no mesmo commit** da fase (allowlist sem
  teste é promessa) e **nenhuma implementação de probe junto**. Fica registrado
  o princípio que sustenta o fail-closed: **a existência de uma API mutável que
  ainda não esteja catalogada não a torna neutra; torna-a proibida.** `docs/29`
  §W1.1 passa a exigir **guarda adjacente a cada chamada** —
  `assert_controlled_write_allowed("create_gvl")` na linha imediatamente
  anterior a `create_gvl`, e o mesmo para `save_as` —, proíbe wrapper genérico
  que receba o nome da operação por parâmetro, e lista o que o manifesto deve
  registrar por operação, incluindo a confirmação de que nenhuma outra operação
  mutável foi solicitada. As fases seguintes (`W1.2` → `create_program`,
  `W1.3` → `replace`, `W1.4` → `build`) ficam documentadas como commits próprios,
  sem antecipar autorização.

### Adicionado
- `docs/28-contrato-escrita-controlada-mastertool-x.md`: contrato **normativo**
  da escrita controlada, escrito depois da evidência e não antes dela. Está
  **fechado quanto ao gate read-only e aberto quanto à escrita** — não autoriza
  mutação nenhuma, e `READ_ONLY_PHASE` permanece `True`. Fixa: projeto
  descartável obrigatório em **diretório próprio** (abrir um projeto cria
  `.opt` irmãos, que numa pasta de produção seriam escritos ao lado do projeto
  real); proibições permanentes por nome, cada uma com o motivo medido, entre
  elas as três descobertas em W0 — `ScriptPromptHandling.SuppressPrompts`
  (suprimir diálogo torna inexequível a regra "diálogo inesperado → cancelar e
  registrar"), `download_missing_libraries` e `set_compilerversion_to_newest`;
  allowlist **literal**, por nome de membro e tipo declarante, sob a regra de
  que **API não catalogada é proibida mesmo que exista e funcione**; plano de
  alteração escrito antes, contra o qual o resultado é conferido; `save_as`
  obrigatório para arquivo novo, com `save()` no lugar dele proibido; **o
  analisador read-only como juiz** — o que não puder ser verificado por ele não
  pode ser escrito; rollback pelo **projeto inteiro**, porque `create_*`
  devolve o objeto já inserido na árvore e não existe desfazer transacional;
  critérios de aborto; e trilha de auditoria que inclui a observação humana do
  que apareceu na tela, que nenhum script produz. Duas regras vieram de defeito
  de método real, não de teoria: o **diff estrutural compara o `.project`, nunca
  a pasta**, e **valor de teste igual ao default não é evidência**. §14 exige
  que a abertura do gate seja um **commit próprio e isolado**, para que apareça
  no histórico como decisão e não como linha perdida dentro de um slice.

### Alterado
- `docs/27` incorpora a **metade de runtime de W0**, medida em sessão
  supervisionada de 2026-07-31: seis execuções, UI visível, offline, sobre
  cópia descartável isolada, **nenhum diálogo, zero processos órfãos e SHA-256
  da cópia idêntico nas seis**. A linha de comando **não mudou** — `--runscript=`,
  `--scriptargs:` e `--project=` na mesma forma do 3.63, e o `--scriptargs`
  continua quebrando o valor em espaço em branco, agora medido no MasterTool X.
  **64 bits deixou de ser inferência** (`IntPtr.Size = 8`,
  `Is64BitProcess = True`), e o módulo real do processo prova que a execução foi
  na instalação 4.1.0 e não na 4.0.0 que também está na máquina. Runtime:
  `platform` `cli`, `version_info` 2.7.12, banner
  `MT9000.exe Mastertool X 4.1.0.11, ScriptEngine.plugin 4.2.0.0` — produto e
  ScriptEngine numa string só, o que nem 3.63 nem 3.70 traziam. 792 assemblies
  no AppDomain, 36 de scripting, todos coerentes com a reflexão estática, com o
  núcleo CODESYS em 3.5.18.60 — o que explica a superfície aditiva. **`probes/15`
  e `probes/21`, escritos para o MT8500 3.63, rodaram sem uma linha alterada**;
  o scan concluiu `complete` com 3 raízes, 34 nós, profundidade 6 e 0 erros, e a
  declaração de segurança do artefato real traz `object_creation`,
  `object_modification`, `project_save`, `device_repository_access`,
  `online_access`, `download` e `force` todos `false`. Ficam registrados os dois
  achados de método — o valor de teste que coincidia com o default e a sobra de
  `pytest` que contamina a busca por artefato (real execução traz `platform`
  `cli`; sobra de teste traz `win32`) — e o que **continua sem medição**:
  `--noUI` (não testado de propósito), diretório do Device Repository (não lido,
  por iniciar comunicação), export mínimo (a cópia é um projeto vazio) e a
  propagação do exit code do script, que segue sem evidência.

### Adicionado
- `scripts/mastertool/probes/26_probe_runtime_identity.py`: probe **somente
  leitura** da Etapa 2 de W0, para medir dentro do processo as quatro coisas
  que a reflexão estática não alcança — **bitness efetivo** (por
  `System.IntPtr.Size` e `Environment.Is64BitProcess`, nunca inferido do
  diretório de instalação, porque um assembly AnyCPU vive em `Program Files` e
  pode rodar em 32 ou 64 bits), **assemblies carregados** no AppDomain (o disco
  mostra o que existe, não o que carrega), o **módulo real do processo** (que
  diferencia a instalação 4.0.0 da 4.1.0) e o `sys.version` cru. Reusa
  `probe_cli.runtime_identity()` em vez de reimplementá-la. Determina a versão
  do ScriptEngine pelo **assembly carregado**, não pelo parse do banner: o
  banner mudou de formato entre 3.63 e 3.70 e supor que o do MasterTool X siga
  o mesmo padrão seria a inferência que este projeto não faz — assembly
  carregado é fato, banner é texto. Do projeto lê **apenas**
  `projects.primary.path`, e **nunca** toca `device_repository`, marcado em
  `common/compatibility.py` como capaz de iniciar comunicação ao ter
  propriedades lidas; o diretório do repositório de dispositivos é
  responsabilidade do host, que o lê do disco. Nenhuma chamada de criação,
  escrita, renome, remoção, importação, `save`, `build` ou online existe no
  arquivo, e cada passo é isolado: uma falha nunca impede os seguintes nem a
  gravação do artefato.
- `common/probe_cli.py` ganha `assembly_name_matches` e
  `scriptengine_version_from_assemblies`, com testes em
  `tests/unit/test_probe_cli.py`. A lógica pura sai do probe porque **probe que
  roda dentro do MasterTool não é testável; módulo comum é** — a mesma razão
  pela qual `probe_cli` existe. O casamento é por **prefixo, não substring**:
  `ScriptEngine` casa `ScriptEngine3`, e um assembly de terceiro chamado
  `MeuScriptEngineFalso` não é nosso. `ScriptEngine3` tem precedência por ser
  onde vivem as interfaces reais (`docs/24`); sem ele a função aceita qualquer
  `ScriptEngine*` e **diz qual usou**; sem nenhum, devolve `None` com o motivo,
  nunca um palpite.

### Adicionado
- `docs/27-reconhecimento-mastertool-x.md`: registro de campo do marco **W0**
  da trilha de autoria controlada. **Nenhum método mutável foi invocado e
  nenhum processo do MasterTool foi lançado** — só metadado de arquivo e
  `Assembly.ReflectionOnlyLoadFrom`. Estabelece por medição, não por suposição:
  a designação "X4.1" é `MT9000.exe` **4.1.0.11** (e o executável deixou de se
  chamar `MT8500.exe`, o que invalida como estão as invocações de `docs/15`,
  `docs/22` e `docs/23`); o runtime de script **não mudou de geração**, segue
  IronPython **2.7.12**, o mesmo do 3.70; e os assemblies de scripting subiram
  de **4.1.0.0 para 4.2.0.0** — ou seja, a conclusão de `docs/26` ("a API não
  mudou") vale para 3.63 × 3.70 e **não** se estende ao MasterTool X. A mudança,
  medida, é **aditiva**: nas 15 sementes que o projeto usa (141 × 140 membros)
  há **uma** sobrecarga a mais (`IScriptProjects6.open_archive` com
  `categories_to_extract`) e **nada removido nem com assinatura alterada**; na
  varredura ampla (304 × 312 tipos, 1.544 × 1.616 membros), das 126 remoções
  112 são `DocuDumper` e as únicas funcionais são `dump_scripting_api`,
  `ISystemForPatches`, os dois diálogos de senha e `ScriptDebuggingMode`.
  Cataloga a superfície de escrita: `create_gvl`, `create_pou`, `create_dut`,
  `create_interface`, `create_persistentvars`, `create_folder`, `create_task`
  (todos idênticos ao 3.70) e os novos `create_program`, `create_function` e
  `create_function_block` de `IScriptIecLanguageObjectContainer4`; linguagem por
  **GUID** de `IScriptImplementationLanguages` e nunca por string; conteúdo
  textual pelo `IScriptTextDocument` devolvido por
  `textual_declaration`/`textual_implementation`, que **não têm setter**; e a
  rota B (`import_xml` com `ConflictResolve` explícito), que deixa de ser
  "permanentemente fora de escopo" e passa a ser **não-autorizada até o
  contrato de W3**. Registra oito riscos, três deles novos e destinados à lista
  proibida — `ScriptPromptHandling.SuppressPrompts` (suprimir diálogo converte
  parada segura em decisão silenciosa), `download_missing_libraries` (faz rede)
  e `set_compilerversion_to_newest` (mutação de alto impacto disfarçada de
  configuração) — mais o conceito **novo** de objeto transiente, que um diff
  estrutural precisa tratar sob pena de acusar criação e remoção que não
  existem. Documenta também a normalização sem a qual a comparação mente: o
  `Version=` embutido em nome de tipo genérico produzia 27 diferenças falsas, e
  comparar só por nome de membro esconderia mudança de parâmetro. Declara duas
  pendências honestas: o instrumento da varredura ampla **ainda não está
  versionado** (emite schema diferente do que `static_api/` consome), e a
  metade de **runtime** de W0 continua aberta — `sys.version`, bitness do
  processo, assemblies carregados, compatibilidade dos probes read-only e,
  antes de tudo, **as opções de linha de comando**, que não são constantes dos
  assemblies e podem ter mudado junto com o nome do executável. Sem elas, nem
  os probes read-only podem rodar. O contrato de escrita controlada passa de
  `docs/27` para **`docs/28`**.

### Alterado
- **Mudança de prioridade do projeto.** O próximo marco passa a ser
  `MasterTool X controlled project authoring` — criar e alterar objetos de
  projeto (POU, GVL e, depois, os demais) de forma controlada dentro do
  MasterTool X instalado nesta máquina, usando o analisador somente leitura já
  existente como mecanismo de verificação do que mudou. A **semântica simbólica
  Ladder (L5) vai para o backlog**: não é descartada e o contrato `docs/21`
  permanece válido e íntegro, mas deixa de ser o caminho crítico. A implementação
  `feat: add Ladder semantic indexing` **não** foi iniciada. Ladder volta em W5,
  aí como validador da lógica criada, e não como entregável independente.
  `docs/18` passa a registrar os seis marcos (W0 reconhecimento → W1 primeira
  mutação mínima → W2 conteúdo textual → W3 transação segura → W4 objetos
  adicionais → W5 Ladder/FBD), as duas rotas de escrita a investigar (API nativa
  e importação controlada), e a regra de que **nada é escrito em projeto
  industrial antes do gate transacional de W3**. Fica registrado também o gate
  que a trilha vai encontrar: `scripts/mastertool/common/safety.py` declara
  `READ_ONLY_PHASE = True` e bloqueia fail-closed exatamente `create_object`,
  `set_declaration`, `set_implementation` e `save_project` — abri-lo é decisão
  própria, com autorização humana explícita, nunca efeito colateral de um slice.
  Nenhuma mudança de código neste slice.
- `docs/18-estado-e-proximo-passo.md` atualizado com o estado real: `HEAD` em
  `40e9c1d`, os cinco commits da trilha de dispositivos que ele ainda não
  registrava, e a suíte remedida nesta árvore — **1418 passed, 1 skipped,
  exit 0** (o número anterior, 1326, era de `8dc3f82`, antes de ~725 linhas de
  teste novas). Ficam anotadas as duas armadilhas de medição encontradas ao
  remedir: rodar `pytest` do diretório pai coleta também o repo sanitizado
  vizinho e morre com 49 erros de coleta (ambiente, não regressão), e como
  `addopts = "-q"` já está no `pyproject.toml`, passar `-q` de novo vira `-qq` e
  o pytest suprime a linha de resumo — a suíte parece não reportar contagem
  nenhuma. O documento passa a trazer também as medições preliminares do
  MasterTool X feitas só por metadados de arquivo, sem lançar processo:
  `MT9000.exe` (não mais `MT8500.exe`), `FileVersion`/`ProductVersion`
  `4.1.0.11`, instalado em `Program Files` de 64 bits, com `ScriptEngine.dll`,
  `ScriptEngine2.dll` e `ScriptEngine3.dll` no mesmo diretório — **sem** o
  sufixo `.plugin` do nome de arquivo das versões 3.x. Nada disso autoriza
  concluir que a superfície de API é a mesma ou diferente: é medição de W0.

### Adicionado
- **Trilha de extração e inventário de dispositivos — ENCERRADA.** Os cinco
  commits `36cb0c2`, `02fe936`, `5d05f82`, `9a405eb` e `40e9c1d` entraram sem
  registro no changelog; ficam registrados aqui em conjunto, com o que cada um
  estabeleceu:
  - `probes/21_scan_project_tree_full.py` + `common/probe_cli.py` (`docs/22`):
    varredura recursiva somente leitura da árvore inteira, isolamento de erro
    por nó, limites **por argumento** (não fixos no módulo como em `probes/12`)
    e saída obrigatoriamente fora do repositório. `truncated` tem precedência
    sobre erro de nó — varredura incompleta jamais é apresentada como completa.
    Num projeto industrial real de 194 nós: `complete`, 4 raízes, profundidade
    máxima 7 (muito abaixo do default 32 — a preocupação com profundidade era
    infundada), zero erros, cópia byte a byte idêntica antes e depois. Achado
    registrado: **`object_guid` não é identidade estável entre sessões** — 4 dos
    194 nós mudam de GUID a cada sessão (referências de POU sob Task
    Configuration e `__VisualizationStyle`), e comparar varreduras por ele
    produz mudança fantasma; `name` e `type_guid` se mantiveram estáveis.
  - `probes/25_export_devices_individually.py` +
    `common/device_export_inspection.py` (`docs/23`): export PLCopen dispositivo
    a dispositivo, porque `export_xml` vive em `IScriptObject` e não só no
    projeto. O export monolítico é um **serializador que falha em silêncio** —
    duas exportações independentes, modos diferentes, 42 minutos de intervalo,
    abortaram no mesmo nó sem fechar `</project>`, e um arquivo de 9 MB parecia
    pronto sem ser. Isolando: 35 dispositivos, 31 exportados, todos fechando o
    elemento raiz, 1742 parâmetros recuperados, e as 4 falhas viram
    `Exception("No devdesc installed for '<nome>'")` nomeadas em vez de destruir
    o arquivo inteiro. O truncamento é medido por dispositivo, não presumido.
  - `probes/22` e `probes/23` (`docs/24`): a API de parâmetros de dispositivo
    investigada e **descartada com evidência**. O elo existe e é alcançável —
    `node.device_parameters` devolve `ScriptMappableDeviceParameterSet`, e o
    padrão de extensão que falhou para Ladder funciona para device — mas
    `Count = 0` em todos os 16 dispositivos com o membro, enquanto o export XML
    dos mesmos dispositivos, no mesmo instante, trazia 1742 `<Parameter>` com
    valor. **Resultado vazio não é ausência de configuração**: é este caminho de
    API que não a alcança. Documentado para que ninguém refaça a investigação
    supondo que nunca foi feita. A Fase 2 (leitura de `parameter.value`) foi
    escrita, nunca executada e **deliberadamente não versionada** — versioná-la
    daria a impressão de caminho suportado onde há beco sem saída medido.
  - `inventory/device_inventory.py` + `tools/build_device_inventory.py`
    (`docs/25`): inventário determinístico construído **offline** a partir dos
    exports por dispositivo e da topologia, sem abrir o MasterTool. Duas camadas
    deliberadamente separadas (bruta, onde nada é descartado; interpretada, só
    onde há evidência estrutural), quatro estados de valor nunca colapsados
    (`presente` inclusive `"0"`, `estruturado`, `vazio`, `ausente`), hierarquia
    de evidência sem nível `low` — nome isolado vira candidato, não fato. Sem
    timestamp nas saídas: duas execuções sobre as mesmas runs dão os sete
    arquivos byte a byte idênticos. O CLI recusa `--output` apontando para
    dentro do repositório com `exit 2` antes de ler qualquer coisa, e recusa
    dispositivo duplicado entre runs a menos que `--prefer-latest-run` torne a
    escolha explícita. Runs de hashes de projeto diferentes produzem
    `inventory_snapshot_kind = "composite"`, que **não** é snapshot forense e
    diz isso no manifesto.
  - `docs/26`: compatibilidade entre versões. A API de scripting **não mudou
    entre 3.63 e 3.70** — catálogo estático byte a byte idêntico, 859 membros
    públicos de `ScriptDriverDeviceObject` com as mesmas chaves; o que muda entre
    versões é o **repositório de dispositivos**, que é por versão instalada
    (`C:\ProgramData\MT8500 <versao>\Devices\<Type>\<Id>\<Version>`, com `Id`
    codificando a identidade CIP). Isso vale para 3.63 × 3.70 e **não** se
    estende ao MasterTool X.
  - **Cobertura final da trilha: 35 de 35 dispositivos.** Instalada a device
    description que faltava — um único EDS resolveu os quatro adaptadores, todos
    o mesmo produto (WEG CFW500, `853_2_3072_4`), o que não era demonstrável
    antes porque os prefixos de nome diferiam e só dois apareciam na lógica —, o
    total subiu para 1894 parâmetros, mais do que o export monolítico truncado
    chegou a escrever. Dois defeitos nossos foram pegos antes de qualquer
    entrega: `<Value>` com filhos (984 de 1894) classificado como vazio, e
    `ParameterId` sozinho promovendo `Supported Functions` a `ip_address` e
    `Dummy Parameter` a `subnet_mask`. **Nenhum dado de cliente foi versionado**
    — só método, regras, testes com fixtures sintéticas e documentação.

### Adicionado
- `docs/21-contrato-semantica-ladder.md`: contrato da camada que transforma
  topologia em símbolos, acessos e chamadas — leitura de contato, escrita de
  bobina com `set`/`reset` preservados, pino declarado `inout` como
  `read_write` (espelhando `var_in_out_resolved` do lado ST), bloco invocado
  como chamada e POU contenedora como caller. Define que a iteração é sobre
  **elementos canônicos** e não sobre nós da topologia (senão elemento em
  `unassigned_elements` perderia o acesso em silêncio); que o texto do símbolo é
  classificado pelo lexer ST que já existe (`indexer/st_lexer.py`) e não por
  regex nova, o que dá literal tipado, número com base e endereço de hardware
  `%IX0.0` de graça; que literal é `not_applicable` com estado `resolved` (a
  designação foi determinada — é um literal) e expressão composta **não** é
  decomposta; que `unresolved` significa "a resolução desta camada não alcança",
  nunca "o símbolo não existe" (global e GVL são Fase L6); e que `confidence`
  **não é campo** do artefato — deriva do `resolution_state` pelo mapeamento
  fixo que já existe em `indexer/query.py`. Três divergências conscientes com
  `docs/14` §L5 ficam registradas: `read_write` é por ocorrência e não por
  símbolo, os cinco JSON do roadmap não são criados enquanto não houver
  consumidor, e o Gate L5 é cumprido no modelo — ligar à CLI exige a resolução
  de símbolo que é a Fase L6. Censo do export real vinculado a
  `(run, sha256)`: 42 elementos, 11 identificadores todos na interface
  declarada, 8 literais, 10 chamadas, **zero pinos `inout`** — e o contrato
  declara quais três regras suas ainda não viram dado real em vez de fingir
  cobertura. Documento apenas: nenhuma mudança em parser, modelo canônico,
  topologia, runners, exportação ou schemas implementados.

### Alterado
- `docs/14-ladder-roadmap.md` §L5 corrigido para não contradizer o contrato novo
  — versionar duas especificações canônicas divergentes criaria ambiguidade
  imediata. A seção passa a apontar `docs/21` como normativa e deixa de
  classificar contato + bobina do mesmo símbolo como uma ocorrência
  `read_write`: são duas ocorrências, `read` e `write`, e o símbolo consta nos
  dois conjuntos (`access_modes` agregado é apresentação, não reclassificação).
  `read_write` fica reservado à ocorrência intrinsecamente bidirecional
  (`VAR_IN_OUT` / pino `inout`); "variável de retenção" deixa de ser
  bidirecional por ser retentiva; e o comparador deixa de "ler operandos" — é
  bloco, produz chamada, e os operandos são elementos próprios que emitem as
  suas leituras. O Gate L5 passa a ser explicitamente de modelo/API interna,
  com `ProjectSymbolIndex`, resolução global, GVL, CLI e mesclagem ST+Ladder
  movidos para a Fase L6, e `resolved` de chamada definido como "callee
  extraído inequivocamente do elemento canônico" — não "alvo existe no
  projeto". Os cinco JSON deixam de ser entregáveis e ficam como registro
  histórico da redação original.
- `docs/18-estado-e-proximo-passo.md` reescrito. Ele é o documento canônico de
  retomada e estava parado em 2026-07-28: dizia "falta a consolidação" quando a
  consolidação havia fechado, a tag `v0.2.0-ladder-structure` sido cortada e a
  topologia lógica entrado. Agora registra `HEAD`, a tag, os quatro commits
  pós-baseline, os números medidos da suíte (1326 passed / 1 skipped, com o
  motivo real do skip), o artefato de referência da POU real com hash, e a
  semântica simbólica como próximo slice. Passa a fixar também a ordem de
  fechamento de slice em nove passos, com o **commit documental antes da
  implementação** (contrato commitado junto do código que deveria reger é
  indistinguível de racionalização escrita depois) e as memórias no penúltimo,
  para não criarem um segundo estado intermediário que envelhece antes do fim —
  foi exatamente assim que este documento ficou cinco dias desatualizado.

### Adicionado
- `src/mastertool_bridge/plcopen/logical_topology.py`: deriva a topologia
  lógica dirigida a partir do modelo canônico (`docs/20`), com constante de
  família própria `LOGICAL_TOPOLOGY_SCHEMA_VERSION`. Nós são **terminais**
  (`net|5|In1`), não elementos; direção vem só de pino declarado ou do contrato
  do tipo, nunca de posição; conexão não resolvida vai para
  `unresolved_connections` e jamais vira aresta — o estado `probable` não
  existe no vocabulário. As duas fontes de evidência continuam separadas mesmo
  sustentando a mesma aresta. Sobre a POU real: 4 redes, 66 nós, 26 arestas,
  6 conexões não resolvidas (todas de fronteira com o trilho), **nenhum
  diagnóstico de severidade `error`** e todas as 32 evidências referenciadas.
  Dois achados registrados no contrato: conexão com elemento fora das redes é
  `unassigned_element_connection` (info) e não `cross_network_connection`
  (error); e ciclos não ocorrem no grafo de terminais porque a aresta interna
  que os fecharia seria uma afirmação de condução — semântica, não topologia.

- `docs/20-contrato-topologia-logica.md`: contrato da camada intermediária
  entre a estrutura canônica e qualquer interpretação de comportamento —
  `LogicalTopology`/`LogicalNetwork`, com **nós como terminais** (`block:18.EN`,
  `contact:12.output`) e não elementos inteiros. Define quando uma direção é
  válida, que conexão não resolvida nunca vira aresta "provável", como redes
  ficam isoladas, que ciclo observado não é programa inválido, e os 11 códigos
  de diagnóstico com severidade separada. Documento apenas: nenhuma mudança em
  parser, modelo canônico, runners, exportação ou schemas implementados.

### Alterado
- Os helpers de escrita de artefatos passam a se chamar `write_json_via_temp` e
  `write_text_via_temp` (antes `*_atomic`). **Nenhuma mudança de
  comportamento** — só o nome deixa de prometer o que o procedimento não
  entrega: escrever `.tmp` → remover o destino → renomear tem uma janela em que
  o arquivo não existe, e IronPython 2.7 não tem `os.replace` para eliminá-la.
  A garantia real (destino nunca pela metade, temporário removido em qualquer
  falha) continua a mesma, agora descrita pelo próprio nome. `docs/16` e
  `docs/19` acompanham. O relatório da baseline não foi alterado: ele registra
  a limitação como ela era observada na época.

### Adicionado
- `tools/verify_plcopen_export_smoke.py`: verificador reutilizável de uma run
  de exportação PLCopen já concluída — read-only, run sempre por `--run-dir`
  (sem caminho padrão, para não verificar silenciosamente a execução errada),
  saída em texto ou `--json`, e códigos de saída distintos para "verificação
  falhou" (1) e "uso inválido / run sem estrutura" (2). Mantém cada afirmação
  na sua fonte: identidade em `target-identity.json`, veredito científico em
  `export-analysis.json`, estado operacional em `status.json`, declaração do
  runner em `output/run-report.json`, e `final_state` do host apenas quando
  fornecido por `--host-report` — sem ele, o verificador diz que não pôde
  conferir em vez de inferir. `result_case=P_created` é explicitamente
  recusado como substituto de `P1_graphical_body_present`: o primeiro é
  vocabulário do probe, o segundo classifica o formato produzido. O modo de
  revisão histórica nunca é automático. Fixture dos testes inteiramente
  sintética, com teste que falha se um identificador real aparecer.

- `scripts/mastertool/common/artifacts.py`: mecanismo comum de escrita dos
  quatro artefatos compartilhados pelas cinco operações supervisionadas
  (`diagnostics.json`, `safety-declaration.json`, `report.md`,
  `checksums.sha256`), extraído da duplicação que era idêntica linha a linha
  nos probes 16–19. Oferece escrita via arquivo temporário
  (`write_json_via_temp` / `write_text_via_temp`): grava um `.tmp`, remove o
  destino e renomeia por cima — o destino nunca fica pela metade, e o
  temporário some em qualquer falha. Geração de checksums com exclusão de
  diretório (o probe 20
  mantém `export-root/` fora, por ter hashes próprios em
  `created-artifacts.json`) e `ArtifactWriteError` com caminho e causa.
  Unifica COMO os arquivos são produzidos, nunca o que significam: nenhum
  schema de safety declaration entrou no módulo, e as duas classes seguem
  separadas. `manifest.json`, `invocation.json`, `target-identity.json`,
  `control-validation.json`, `created-artifacts.json` e `extension-items.json`
  continuam sob responsabilidade de cada operação. Equivalência verificada
  chamando `_write_artifacts` real dos cinco probes antes e depois, no mesmo
  diretório: artefatos **byte a byte idênticos** nos cinco.
- `src/mastertool_bridge/automation/run_states.py`: fonte única dos **estados
  operacionais** no lado host — uma constante por estado, `VALID_STATES`,
  `TERMINAL_STATES` e as transições. O vocabulário já existia completo no
  runner interno (`run_status.py`); faltava ao host, que só tinha os terminais
  e espalhava o resto como literal. Os dois runtimes não podem se importar
  (IronPython 2.7 × CPython 3.11), então as declarações são espelhadas e
  `tests/unit/test_run_states.py` falha se divergirem, inclusive na ordem.
  `result_models.TERMINAL_STATES` era uma terceira cópia e virou reexportação.
  `OBSERVED_TRANSITIONS` foi derivada de **10 execuções reais arquivadas**, não
  desenhada — e `unobserved_transitions()` sinaliza em vez de reprovar, sem
  nada imposto no caminho de escrita do runner interno. Estado operacional
  segue separado de resultado científico: há teste garantindo que `P1`–`P4`,
  `E1`–`E4`, `S1`–`S3`, `resolved`, `ambiguous` e afins nunca entrem no
  vocabulário operacional.

### Alterado
- Versões de schema passam a ser declaradas **por família de artefato**, com
  constante própria em cada contrato: `STRUCTURE_MAP_SCHEMA_VERSION`,
  `ANALYSIS_SCHEMA_VERSION`, `REVISION_SCHEMA_VERSION` e
  `RECLASSIFY_SCHEMA_VERSION` (novas), somadas às já existentes de
  configuração de run, resposta de consulta e modelo canônico. Literais soltos
  eliminados dentro da família inteira, inclusive os dois de `indexer/query.py`.
  **Nenhuma conversão em massa**: a família de probe/export do IronPython
  continua em `"1.0"` string — é o formato de 29 arquivos e está formalizado
  nos cinco JSON Schemas — e o `"2.0"` do dump de API do ScriptEngine
  permanece intacto, por ser contrato próprio. Não existe constante global de
  versão: as famílias coincidem no valor hoje e precisam poder divergir sem
  uma arrastar a outra. Nenhum leitor aceita a versão de outra família; runs
  arquivadas não foram reescritas. Ver `docs/19-contratos-de-execucao.md`,
  seção 7, e `tests/unit/test_schema_version_families.py`.

### Corrigido
- A exportação controlada passa a arquivar `target-identity.json` — artefato
  próprio, com `schema_version` inteiro, coberto por `checksums.sha256`. Era a
  única das cinco operações supervisionadas que validava a identidade do alvo
  sem arquivá-la: a operação de maior risco tinha a rastreabilidade mais fraca.
  Escrito em três pontos (identidade confere, identidade diverge, e aborto
  anterior à guarda de identidade), sempre derivado do `result` e portanto
  idempotente. `identity_check_reached` distingue "o alvo não confere" de
  "nunca chegamos a olhar o alvo" — duas situações que sem ele ficariam
  idênticas. A ausência do arquivo é **aviso** em revisão de run arquivada
  (`archived_revision=True`, usado por `host_validation_revision.revise_run()`)
  e continua **erro** em run nova; o modo histórico perdoa apenas os nomes de
  `PLCOPEN_EXPORT_FILENAMES_INTRODUCED_LATER`, nunca um artefato que já era
  exigido. Runs arquivadas não são reescritas.
  **Pendente de smoke supervisionado**: o código alterado roda dentro do
  MasterTool e não foi executado.

### Adicionado
- `docs/19-contratos-de-execucao.md`: contratos estáveis de estado
  operacional, resultado científico, procedência, identidade, safety
  declaration, validação de artefatos, versionamento de schema e campos
  comuns entre operações read-only e exportação controlada (frente 3 da
  consolidação). Registra o núcleo comum MEDIDO (quatro artefatos nas cinco
  operações), duas divergências a resolver antes de qualquer abstração — a
  exportação valida identidade mas não arquiva `target-identity.json`, e
  `schema_version` convive como string `"1.0"` e inteiro `1` — e o que **não**
  deve ser abstraído, com o motivo de cada caso.
- `scripts/host/run_supervised_snapshot.ps1`: seam de ensaio
  `MASTERTOOL_BRIDGE_FAKE_PROCESS_LIST` para a detecção de MasterTool aberto,
  consultado **somente** quando `-Execute` está ausente — com `-Execute` o
  ramo simulado é estruturalmente inalcançável e `Get-Process` sempre governa.
  Formato `<nome-da-imagem>:<pid>` separado por `;`; string vazia significa
  nenhum processo; entrada malformada **reprova fail-closed**, nunca degrada
  para "nada aberto". Espelha o seam `process_lister` que já existia em
  `automation/supervised_run.py`. Ver `docs/16-supervised-runner-contract.md`.
- `src/mastertool_bridge/plcopen/ladder_parser.py`: `parse_ladder()` liga
  `structure_map` (schema real observado) a `canonical_model` (tipos e
  invariantes), produzindo um `GraphicPOU` validado a partir de um PLCopen
  XML Ladder. IDs determinísticos e estáveis para elementos, pinos,
  evidências, arestas, componentes, redes e extensões do fornecedor. Pino de
  origem só é resolvido contra os pinos declarados pelo bloco de origem —
  nunca pelo `formalParameter` cru da conexão, que é preservado como
  evidência bruta em todos os casos, inclusive quando conflitante entre
  fontes de evidência distintas. As duas fontes de topologia
  (`plcopen_connection` e `vendor_parallel_branch`) nunca são fundidas. Rede
  é reconstruída por dois sinais independentes (marcador `networktitle` do
  fornecedor e conectividade sem trilhos). `write_canonical_pou()` grava o
  JSON canônico de forma determinística.
- `tests/unit/test_plcopen_ladder_parser.py`: cobre taxonomia e contagem de
  elementos, separação das duas fontes de evidência, a anomalia real do
  `formalParameter` que não é pino de saída declarado, `TON`/`instanceName`
  vs. operadores sem instância, `value_source_kind` variável vs. expressão,
  reconstrução de redes, determinismo e round-trip `to_dict`/`from_dict`.
  Roda também contra o export real quando disponível localmente (nunca
  versionado), com asserções puramente estruturais.

### Alterado
- `tests/unit/test_supervised_snapshot_wrapper.py`: os três testes do wrapper
  não pulam mais conforme haja MasterTool aberto na máquina — passam a usar o
  seam de ensaio e rodam de forma determinística. Acrescentados testes para o
  bloqueio com processo simulado e para a reprovação fail-closed com variável
  malformada. O `skipif` de `powershell` ausente permanece: é limitação de
  plataforma, não de estado da máquina.
- `src/mastertool_bridge/plcopen/canonical_model.py`: `"comment"` acrescentado
  a `ELEMENT_KINDS` e `OBSERVED_ELEMENT_KINDS` — observado no export real (5
  elementos `<comment>`); já reconhecido por `structure_map.KNOWN_LD_ELEMENTS`,
  então mapeá-lo para `"unknown"` afirmaria não-reconhecimento onde há
  reconhecimento.

## [0.1.0] - 2026-07-23

### Adicionado
- Estrutura inicial do repositório (primeira entrega — Fase 0, somente leitura).
- Scripts IronPython de descoberta: `00_smoke_test`, `01_discover_environment`,
  `02_dump_api_surface`, `03_list_project_tree`.
- Módulos comuns IronPython (`scripts/mastertool/common/`).
- CLI externa `mastertool-bridge` com `validate-export`, `inspect`, `index`,
  `find-symbol`, `find-reads`, `find-writes`, `compare`, `analyze`,
  `build-agent-context`, `validate-change-set`.
- Schemas JSON iniciais (manifesto, objeto, compilação, referências, change set).
- Política de segurança (`config/safety-policy.yaml`) e documentação (`docs/`).
- Testes unitários da camada externa.

### Segurança
- Modo somente leitura obrigatório; importação (`09`–`11`) desabilitada por projeto.

# Contrato da Etapa B — runner supervisionado

> Fonte única de verdade do acordo entre os **dois lados** da Etapa B. Escrito
> ANTES da implementação, de propósito: os dois lados são desenvolvidos em
> paralelo e, sem contrato fixo, cada um inventaria o seu próprio formato de
> `run-config.json` e `status.json`.
>
> - **Lado host** (Python 3.11): `src/mastertool_bridge/automation/`
> - **Lado interno** (IronPython 2.7, roda dentro do MasterTool):
>   `scripts/mastertool/automation/`
>
> Nenhum dos lados importa o outro. O único acoplamento são os arquivos
> descritos aqui.

## 0. Base factual (Etapa A, comprovada em runtime — não presumir nada além)

| Fato | Consequência para o desenho |
|---|---|
| `--project` e `--runscript` preservam caminhos **com espaços** | O repositório pode continuar em `Pasta Com Espacos` |
| `--scriptargs` **quebra o valor em espaços** | **Proibido** passar caminho por `--scriptargs`. O `run_dir` é descoberto via `__file__` |
| `projects_available`/`primary_available` vêm `True` **sem projeto aberto** | Só `projects.primary.path` prova identidade de projeto |
| `cwd` do processo é `C:\WINDOWS\system32` | **Nunca** usar caminho relativo nem `os.getcwd()` |
| Procedência: dentro do MasterTool ⇒ `platform=="cli"`, `IronPython`, `version_info[:2]==[2,7]` | Primeira checagem do runner interno |

## 1. Diretório de execução (autossuficiente)

```text
C:\mastertool-bridge-runs\<run-id>\
├── bootstrap.py            # gerado pelo host; é o alvo do --runscript
├── run-config.json         # gerado pelo host; entrada do runner interno
├── status.json             # escrito pelo runner interno (estado corrente)
├── status-history.jsonl    # escrito pelo runner interno (append-only)
├── logs\
│   └── runner.log
└── output\                 # todos os artefatos de aquisição
```

`<run-id>` = `YYYY-MM-DD_HH-MM-SS` (mesmo formato de `common/file_io.timestamp()`).

## 2. `run-config.json` (host escreve, interno lê)

```json
{
  "schema_version": 1,
  "run_id": "2026-07-24_17-30-00",
  "mode": "supervised_snapshot",

  "repo_root": "C:\\...\\mastertool-rankine-bridge",
  "mastertool_scripts_dir": "C:\\...\\mastertool-rankine-bridge\\scripts\\mastertool",

  "expected_project_path": "C:\\...\\_descartavel\\ExemploPlanta V1.0 COPIA.project",
  "expected_project_sha256": "E278D1C2...688C4E",

  "expected_application_name": "Application",
  "expected_application_guid": "00000000-0000-0000-0000-000000000001",
  "expected_application_type_guid": "639b491f-5557-464c-af91-1471bac9f549",

  "run_dir": "C:\\mastertool-bridge-runs\\2026-07-24_17-30-00",
  "output_dir": "C:\\mastertool-bridge-runs\\2026-07-24_17-30-00\\output",
  "allowed_output_root": "C:\\mastertool-bridge-runs",

  "operations": {
    "scan_project_tree": true,
    "export_text": true,
    "inventory_graphic_objects": true,
    "build": false,
    "save": false,
    "online": false
  }
}
```

### 2.1 `limits` — limites de travessia (opcional; defaults são os validados)

```json
"limits": {
  "scanner":   {"max_depth": 8, "max_total_nodes": 2000, "max_children_per_node": 128,
                "expected_root_count": null},
  "exporter":  {"max_depth": 8, "max_total_nodes": 1000, "max_children_per_node": 128,
                "max_text_objects": 300, "max_document_characters": 1000000,
                "max_total_characters": 15000000},
  "inventory": {"max_depth": 8, "max_total_nodes": 1000, "max_children_per_node": 128}
}
```

**Esta seção foi acrescentada depois da primeira implementação**, e a lacuna
era do contrato, não de quem implementou: sem ela, o runner construía os
motores sem argumentos e caía nos **defaults das classes**, que são mais
frouxos que os validados na baseline `v0.1.0` (scanner `max_total_nodes`
5000 em vez de 2000; exportador `max_text_objects` 500 em vez de 300;
`max_total_characters` 25M em vez de 15M) — e perdia `expected_root_count`
por completo.

Nada disso mudaria os números do `ExemploPlanta` (92 nós está longe de qualquer
teto). O problema é outro, e é duplo: (a) trocar silenciosamente uma
configuração validada por outra não validada quebra a reprodutibilidade
contra a baseline; (b) limites de travessia são a guarda contra varredura
descontrolada, e o runner é **genérico** — vai encontrar projetos
desconhecidos, que é exatamente onde a guarda mais frouxa pesa.

Regras:

- os defaults acima são os valores dos **probes validados** (12, 13 e 14),
  não os das classes;
- chave desconhecida em qualquer um dos três blocos **reprova** o config
  inteiro (mesmo critério fail-closed de `operations`);
- todo valor deve ser inteiro positivo; `expected_root_count` é o único que
  aceita `null`;
- `expected_root_count` tem default `null` (sem validação) porque `4` é
  específico do `ExemploPlanta` — embuti-lo no runner genérico seria o mesmo
  erro de hardcodar os GUIDs da Application (seção 6.3). Quando vier
  preenchido, é repassado ao scanner;
- os três construtores recebem os limites **explicitamente**; nenhum pode
  ser chamado sem argumentos de limite;
- os limites efetivamente usados são registrados em
  `output/run-report.json` (campo `limits_used`), para um snapshot ser
  auditável depois quanto a com que limites foi produzido.

Regras gerais:

- `mastertool_scripts_dir` existe porque o `bootstrap.py` precisa tornar
  `common`/`automation` importáveis **sem depender de `cwd`** (que é
  `system32`) e **sem `--scriptargs`**.
- Os três campos `expected_application_*` existem porque um dos critérios de
  aborto é "identidade da `Application` divergir". Sem eles no config, o
  runner teria que hardcodar GUIDs de um projeto específico — proibido.
- `expected_project_sha256` é a pré-condição: o host calcula antes de abrir;
  o interno **não** recalcula (não lê o arquivo do projeto). Quem confere o
  hash final é o host, depois de fechar.
- `run_dir` aparece no config por redundância de auditoria, mas o runner
  interno **usa o valor derivado de `__file__`** e **aborta se divergir** —
  o config nunca é autoridade sobre onde ele está.

## 3. `operations` — o que é permitido

O runner interno deve **rejeitar** o config (estado `failed`, sem executar
nada) se qualquer uma destas for `true`:

```text
build, save, online, download, force
```

Chaves desconhecidas em `operations` também **reprovam** (fail-closed: uma
operação que o runner não conhece não pode ser silenciosamente ignorada).

A rejeição **reutiliza** `common/safety.py` — `assert_operation_allowed()` e
`SafetyError`, que já existem e já mapeiam `save_project`, `download_to_plc`,
`go_online`, `force_variables` etc. **Não criar uma segunda guarda de
segurança paralela.**

## 3.1 `probe_ladder_surface` — operação da Fase L1 (adicionada 2026-07-24)

Nova chave em `operations`, com entrada **explícita** na whitelist fail-closed
de `run_config.py`:

```json
"operations": {
  "scan_project_tree": false,
  "export_text": false,
  "inventory_graphic_objects": false,
  "probe_ladder_surface": true
}
```

**Não reaproveitar `inventory_graphic_objects`.** Aquele nome representa
*inventário* (classificação de 92 objetos já conhecidos); este representa
*descoberta experimental de superfície de API* sobre um objeto único.
Misturá-los tornaria impossível saber, olhando um `run-config.json`
arquivado, qual capacidade foi de fato autorizada naquela execução.

### Operação `probe_ladder_dynamic_surface` (Fase L1, probe 17)

```json
"operations": {
  "probe_ladder_dynamic_surface": true
}
```

**Independente de `probe_ladder_surface`, e deliberadamente.** As duas
sondam o mesmo objeto por métodos diferentes — o probe 16 por reflexão CLR
(`GetType().GetProperties()/GetMethods()`), o probe 17 pela superfície
dinâmica do IronPython (`dir()` + `hasattr()` controlado). O probe 17 existe
porque a reflexão pura **não vê** as extensões que o ScriptEngine anexa em
runtime: `textual_declaration` é funcional (o `ReadOnlyTextExporter` o usa)
e mesmo assim nunca apareceu na enumeração do probe 16.

Comparar os dois métodos é o objetivo da fase, então cada um precisa poder
ser ligado isoladamente. Uma flag compartilhada tornaria impossível
reproduzir só uma das sondagens a partir de um `run-config.json` arquivado.

Saída em `output/ladder-dynamic-surface/` (diretório próprio, mesmo motivo).

**Critério de validade.** O membro `textual_declaration` é o controle: se a
superfície dinâmica não o reencontrar, o resultado é
`dynamic_probe_inconclusive` e **nenhuma conclusão sobre ausência de API
Ladder é permitida** — um método que não enxerga o membro conhecido não
pode ser usado para afirmar que outro membro não existe. O artefato
`control-validation.json` registra o veredito, e o runner interno imprime
`[ATENCAO]` explícito quando ele é `false`, para que um resultado
inconclusivo nunca se pareça com sucesso na aba de Mensagens.

### Seção `ladder_dynamic_probe` (obrigatória quando `probe_ladder_dynamic_surface` é `true`)

Mesmos quatro campos da seção `ladder_probe`, mesma regra fail-closed nas
duas direções (operação ligada sem seção reprova; seção presente com
operação desligada também reprova).

```json
"ladder_dynamic_probe": {
  "target_node_id": "application/9/4",
  "expected_name": "...",
  "expected_guid": "...",
  "expected_type_guid": "..."
}
```

**Sem default de identidade no modo supervisionado.** O wrapper
`run_supervised_snapshot.ps1` traz os quatro parâmetros
`-LadderDynamic*` **vazios**, ao contrário dos `-Ladder*` do probe 16: um
default preenchido transformaria "esqueci de informar o alvo" numa execução
silenciosa contra o alvo de outra pessoa. Defaults embutidos permanecem
apenas no modo standalone do probe, para desenvolvimento.

### Seção `runtime` de `run-report.json` (procedência)

```json
"runtime": {
  "platform": "cli",
  "runtime_family": "IronPython",
  "version_info": [2, 7, 12],
  "provenance_confirmed": true
}
```

O host valida a procedência lendo exatamente estas chaves. **Ela não era
emitida** até 2026-07-28: `_build_run_report()` produzia só os 6 campos da
declaração mais `limits_used`, e o host, não encontrando `runtime`,
reprovava toda execução. Consequência: desde a Etapa B, toda run
supervisionada real terminou `final_state=failed` por um motivo sem relação
com a aquisição — e uma checagem que sempre falha treina o operador a
ignorar o status, que é o pior resultado possível para uma guarda.

Os valores vêm de `_check_provenance()`, **nunca recalculados** — uma
segunda detecção divergiria da primeira, e a divergência apareceria como
dois vereditos sobre a mesma execução. São **preservados mesmo quando a
procedência reprova**: o host precisa distinguir "rodou em CPython 3 fora do
MasterTool" de "campo ausente". A seção é emitida também nos caminhos de
abort controlado, pelo mesmo motivo.

Códigos de recusa do host, deliberadamente distintos:

| `reason_code` | Significado |
|---|---|
| `runtime_provenance_missing` | seção ausente — **ausência de prova**, não prova de execução externa |
| `runtime_provenance_mismatch` | valores presentes e errados — a ameaça que a checagem existe para pegar |

Campo ausente continua **reprovando** (fail-closed): a correção nunca
converte ausência em sucesso.

### Operação `probe_ladder_extender_surface` (Fase L1, probe 18)

Terceiro canal: `Extender`/`IExtendedObject` — providers e descriptors. O
membro CLR `Extender` estava entre os 29 que a reflexão do probe 16
enxergou; a hipótese é que ele explique a **origem** dos membros dinâmicos
que nem a reflexão nem o `dir()` alcançaram.

**Critério de validade**: reencontrar `textual_declaration` por um caminho
estrutural que passe pelo `Extender`
(`proxy → Extender → provider/descriptor → membro`), registrado em
`known-control-discovery.json` como `discovery_path`. Conseguir refletir
sobre o `Extender` **não** valida o canal, e repetir
`hasattr(proxy, "textual_declaration")` também não — isso o probe 17 já
provou e não demonstra origem.

`extender_channel_validated` exige as três condições simultâneas
(`extender_accessible`, `extension_channel_enumerable`,
`control_provider_found`). Casos:

- **E1**: canal validado, 0 candidatos → conclusão limitada ao canal
  examinado, nunca ausência global de API Ladder;
- **E2**: canal validado + candidatos → abre o próximo probe;
- **E3**: `Extender` acessível mas canal não validado → `inconclusive`;
- **E4**: `Extender` inacessível → `inconclusive`.

**E3/E4 são execuções corretas que não confirmaram o canal.** O status
operacional segue `completed`; o resultado semântico é que é inconclusivo.
O runner **não** converte E3/E4 em `failed` — confundir os dois faria uma
investigação bem executada parecer falha de infraestrutura. O runner imprime
`[ATENCAO]` explícito para o operador não ler como sucesso.

Saída em `output/ladder-extender-probe/`. Seção de config:
`ladder_extender_probe`, mesmos quatro campos e mesma regra fail-closed nas
duas direções.

### Operação `probe_plcopen_export_signature` (Fase L1, probe 19)

Reflete a assinatura **completa** de `export_xml` — optionality, defaults,
`out`/`ref`, position — **sem invocá-lo**. Gate próprio: comprovar a
assinatura sem executar o método.

Seção `plcopen_export_signature_probe`: os mesmos quatro campos de
identidade **mais** `inspect_active_application` (booleano estrito; ausente
vale `true`). Não reutiliza `LadderProbeConfig`, que valida exatamente
quatro strings — um quinto campo aceito e silenciosamente ignorado seria o
mesmo defeito que `KNOWN_OPERATION_KEYS` existe para impedir.

**Dois escopos, mantidos separados**: `export-xml-overloads.json` (POU) e
`active-application-overloads.json` (Application). Cada um classificado por
si — um `S1` num escopo **não** promove o outro. Fundir as listas esconderia
de qual escopo veio a sobrecarga segura, que é justamente o que decide a
primeira exportação.

Com `inspect_active_application=false`, o escopo registra `attempted=false`
e `found=null` — **nunca** `found=false`, que significaria "procurei e não
achei". Confundir "não procurei" com "não existe" é o erro que já custou
duas reclassificações nesta trilha.

`S2`/`S3` são execuções corretas que não comprovaram sobrecarga invocável:
resultado semântico inconclusivo, **não** falha operacional. `final_state`
segue `completed`; a exportação permanece não autorizada.

Esta operação **não escreve nada**: a `safety-declaration` mantém as 10
chaves todas `false`. A mudança de perfil de segurança (escrita em
diretório descartável) pertence à fatia seguinte, e antecipá-la aqui
tornaria a declaração falsa.

### Operação `export_plcopen_xml` (Fase L1, exportação controlada)

**Primeira operação do projeto que ESCREVE.** Escrita permitida: apenas
criação dentro do diretório descartável da run. Escrita proibida: projeto,
`.project`, configuração, hardware, objetos da árvore.

#### Guarda de diretório, não de extensão

O contrato anterior exigia que `stPath` terminasse em `.xml`. **Isso foi
substituído**, e a mudança veio de dado novo: a execução real do probe 19
confirmou a sobrecarga de 4 argumentos, mas a semântica de `stPath` —
arquivo ou diretório — permaneceu desconhecida. O nome é genérico e a
presença de `bExportFolderStructure` sugere que a API pode produzir árvore.
Exigir `.xml` seria adivinhar.

Regra vigente:

```text
stPath precisa apontar para um alvo INEXISTENTE,
dentro de um diretório descartável VAZIO e autorizado.
```

O **runner interno** cria `output/plcopen-export/export-root/` **depois** de
`output_dir` passar na guarda de "vazio", e o **probe 20** apenas confere que
existe, está vazio, é caminho autorizado e não é reparse point.

A criação era do host, antes do lançamento — e isso **quebrou** na run
`2026-07-28_11-37-05`: o runner interno exige `output_dir` vazio ao iniciar
(guarda desde a Etapa B, contra sobrescrever run anterior), então qualquer
coisa pré-criada sob `output/` abortava toda a execução. Duas invariantes
corretas colidiam.

A correção move a criação no ciclo de vida sem enfraquecer guarda nenhuma. O
diretório passa a nascer vazio **por construção** — garantia mais forte que
criá-lo antes e conferir depois. A separação "quem cria não é quem valida"
continua: runner cria, probe valida. `export-root-preparation.json` registra
quem criou e em que ponto, para o artefato arquivado não depender de
memória.

Isso cobre as duas semânticas possíveis e transforma a própria exportação em
experimento controlado sobre `stPath`.

#### A única chamada autorizada

```python
target.export_xml(st_path, False, False, False)
```

Pelo membro conhecido, com quatro argumentos explícitos — **nunca**
`MethodInfo.Invoke()`. Uma execução, uma invocação. Os três booleanos
existem na config para **auditoria** (um `run-config.json` arquivado precisa
dizer com que argumentos a exportação correu), não para abrir matriz de
execução: qualquer valor diferente de `false` reprova.

#### `safety-declaration` com schema próprio

Única declaração do projeto em que campos `true` são esperados:

```json
{"export_xml_called": true, "export_xml_call_count": 1,
 "filesystem_output_written": true,
 "filesystem_output_scope": "authorized_disposable_export_root",
 "project_save_called": false, "project_build_called": false,
 "text_document_write_called": false, "import_called": false,
 "online_operation": false, "download_called": false, "force_called": false}
```

`write_called: false` é **proibido** aqui — seria falso, um XML é escrito. A
validação host-side rejeita a chave.

#### `target-identity.json` — identidade arquivada

A exportação sempre validou a identidade do alvo (aborta com
`target_identity_mismatch`), mas até a consolidação era a única das cinco
operações que não a **arquivava** em artefato próprio: a informação vivia no
`report.md` e no resultado, fora do `checksums.sha256`. A operação de maior
risco tinha a rastreabilidade de alvo mais fraca
(`docs/19-contratos-de-execucao.md`, seção 4).

```json
{"schema_version": 1, "target_node_id": "application/<i>/<j>",
 "name": "<nome do alvo>", "guid": "<guid>", "type_guid": "<type guid>",
 "is_folder": false, "identity_confirmed": true,
 "identity_check_reached": true, "mismatches": []}
```

`schema_version` é **inteiro**, nunca a string `"1.0"`.

Escrito em **três pontos**, sempre a partir do `result` e portanto idempotente
por construção — sem cache nem flag de "já escrevi":

1. logo após a Guarda 4, quando a identidade **confere** — antes da Guarda 5 e
   muito antes da invocação, para que o artefato sobreviva mesmo se o processo
   morrer durante `export_xml`;
2. logo após a Guarda 4, quando a identidade **diverge** — antes do `_abort`,
   com `identity_confirmed: false` e `mismatches` nomeando os campos;
3. dentro de `_write_artifacts()`, cobrindo o aborto **anterior** à Guarda 4.

`identity_check_reached` distingue duas situações que de outro modo ficariam
idênticas: *o alvo não confere* e *nunca chegamos a olhar o alvo*. Ambas dão
`identity_confirmed: false`; só o segundo campo separa as duas.

Não duplica assinatura nem argumentos de `export_xml` — isso é papel de
`invocation.json`. Não depende de `report.md`.

**Runs arquivadas antes desta mudança:** a ausência do arquivo é **aviso**, não
erro, quando a validação roda em modo revisão histórica
(`validate_output_artifacts(..., archived_revision=True)`, usado por
`host_validation_revision.revise_run()`). Numa run **nova** a ausência continua
reprovando. Os nomes com esse tratamento estão em
`PLCOPEN_EXPORT_FILENAMES_INTRODUCED_LATER` — o modo histórico perdoa só esses,
nunca um artefato que já era exigido. Runs arquivadas não são reescritas: estão
cobertas por checksums e refazer a aquisição é proibido.

#### Análise offline, depois do MasterTool fechar

`xml-files.json`, `xml-structure-inventory.json` e `target-object-match.json`
são produzidos pelo **host**, em CPython, com os bytes já congelados — e
**somente** quando a aquisição de fato ocorreu. Precondições, todas
obrigatórias:

```text
internal_status.state == completed
invocation.json existe e export_xml_called == true
created-artifacts.json existe
safety-declaration.json existe
```

Faltando qualquer uma:

```text
offline_analysis: {attempted: false, skipped: true,
                   reason: "acquisition_not_completed"}
```

e **nenhum** dos quatro artefatos é gerado. Rodar a análise sobre um
`export-root` que nunca foi usado produz arquivos que *parecem* resultado e
não são — foi o que aconteceu na run `2026-07-28_11-37-05`. "Não houve o que
analisar" e "analisei e não achei nada" são conclusões opostas.
Interpretar dentro do IronPython decidiria o formato no mesmo processo que o
produziu, e erro de parsing viraria erro dentro do MasterTool. Os arquivos
exportados permanecem byte a byte intactos.

Detecção por **bytes** (não por extensão — `stPath` podia produzir nome sem
`.xml`) e por **URI de namespace** (não por prefixo, que é escolha do
documento).

#### Estado operacional × resultado científico

| `export_result` | significado | `final_state` |
|---|---|---|
| `P1_graphical_body_present` | XML com corpo gráfico | `completed` |
| `P2_declaration_only` | PLCopen válido sem corpo gráfico | `completed` |
| `P3_no_output` | nada produzido | `completed` |
| `P4_unrecognized_format` | formato não reconhecido | `completed` |

Só produzem `failed`: `export_invocation_failed`, `project_copy_modified`,
`runtime_provenance_mismatch`, `target_identity_mismatch`,
`artifact_validation_failed`, `output_escaped_export_root`.

### Detecção de MasterTool aberto — e o seam de ensaio

O wrapper bloqueia antes de montar qualquer comando quando há instância do
MasterTool aberta (`Get-Process -Name 'MT8500*'` → `[BLOQUEADO] Ha
instancia(s) do MasterTool`, `exit 2`).

Essa guarda tornava os testes do wrapper dependentes do estado da máquina:
com o MasterTool aberto, três testes pulavam e a cobertura caía em silêncio.
Desde a consolidação existe um seam **restrito ao modo de ensaio**:

| | |
|---|---|
| Variável | `MASTERTOOL_BRIDGE_FAKE_PROCESS_LIST` |
| Formato | lista separada por `;`, cada item `<nome-da-imagem>:<pid>` |
| String vazia | nenhum processo aberto |
| Exemplo | `MT8500.exe:4242` |
| Malformada | **reprova fail-closed** (`exit 2`), nunca vira "nada aberto" |

**A variável só é consultada quando `-Execute` está ausente.** A negação está
embutida na própria expressão que escolhe a fonte da lista, então com
`-Execute` o ramo simulado é *estruturalmente inalcançável* — não existe
combinação de argumentos que faça uma lista simulada valer numa execução
real, e a checagem via `Get-Process` sempre governa.

A escolha por variável de ambiente, em vez de um parâmetro
`-SimulateProcessList`, é deliberada: um parâmetro criaria a combinação
`-Execute` + simulação, cuja rejeição só poderia ser testada executando o
caminho que lança o MasterTool — e lançar processo GUI contra arquivos reais
exige supervisão visual humana. Aqui não há caminho perigoso a testar porque
não há caminho.

O seam espelha `process_lister` de
`src/mastertool_bridge/automation/supervised_run.py`, que já resolvia o mesmo
problema do lado Python. Entrada inválida reprova nos dois: silêncio sobre
entrada malformada é como uma guarda começa a mentir.

### Exclusão mútua das operações de investigação

`probe_ladder_surface`, `probe_ladder_dynamic_surface`,
`probe_ladder_extender_surface`, `probe_plcopen_export_signature` e
`export_plcopen_xml` **não podem ser ligados na mesma run**. A lista é literal e explícita, não
abstraída — mais auditável nesta fase.
Cada um investiga um canal distinto e carrega gate de validade próprio;
combiná-los produziria vereditos concorrentes sob um único `status` —
ambiguidade justamente no registro que serve de auditoria. A recusa é
aplicada em três camadas independentes (wrapper PowerShell, CLI e
`RunConfig`, além do runner interno), cada uma falhando no ponto mais barato
que alcança.

### Estado `probing_ladder_extender_surface`

Estado dedicado pelo mesmo motivo do probe 17: gate próprio. Cada estado
marca uma fronteira operacional real, o que permite identificar onde a
execução parou, distinguir timeout de falha semântica e manter artefatos
históricos autoexplicativos:

| Estado | Canal investigado |
|---|---|
| `scanning` (probe 16) | reflexão CLR do proxy |
| `probing_ladder_dynamic_surface` | `dir()` e acesso dinâmico por nome |
| `probing_ladder_extender_surface` | `Extender`, providers e descriptors |

Um estado genérico (`probing_ladder_discovery` com subestado) só faria
sentido se houvesse um orquestrador único executando os três como operação
composta — abstração deliberadamente **não** introduzida agora, já que os
probes são operações independentes.

### Estado `probing_ladder_dynamic_surface`

O probe 16 reutilizou `scanning` por não haver estado dedicado. O probe 17
ganhou o seu porque tem um **gate de validade próprio** cujo resultado
decide se a Fase L1 avança; fundi-lo a `scanning` apagaria essa distinção no
`status-history.jsonl`, que é o registro de auditoria da execução. O estado
não é terminal — a execução segue para `validating`/`completed`.

### Seção `ladder_probe` (obrigatória quando `probe_ladder_surface` é `true`)

```json
"ladder_probe": {
  "target_node_id": "application/9/4",
  "expected_name": "FB_PISCA_EXEMPLO",
  "expected_guid": "00000000-0000-0000-0000-000000000002",
  "expected_type_guid": "6f9dac99-8de1-4efc-8465-68ac443b7d08"
}
```

Ausente quando a operação está ligada ⇒ `failed`. Presente quando a operação
está desligada ⇒ também `failed` (config incoerente não é aceito por
omissão).

**Nenhum destes valores pode ser hardcoded** no probe ou no runner — todos
vêm do config, mesma regra dos `expected_application_*` (seção 6.3).

### Identificação do alvo — os quatro `expected_*` não são redundantes

Os 25 candidatos da Fase L0 **compartilham o mesmo `type_guid`**
(`6f9dac99-8de1-4efc-8465-68ac443b7d08`, o tipo POU — o mesmo do `MainPrg`,
que é `supported`). Verificado no inventário real de 2026-07-24 15:56.
Portanto:

- `type_guid` **não** identifica o alvo, só confirma que é um POU;
- `object_guid` é o identificador forte e estável;
- `node_id` é posicional e pode mudar se a árvore for reorganizada;
- `name` é legível mas não é único por construção.

Por isso a checagem exige **os quatro juntos**, nesta ordem, antes de
qualquer sondagem:

```text
localizar node_id -> conferir nome -> conferir object_guid
-> conferir type_guid -> confirmar is_folder == false -> so entao inspecionar
```

Qualquer divergência aborta com `target_identity_mismatch`, sem sondar nada.

### Alvo da primeira execução, escolhido por evidência

`application/9/4` — `FB_PISCA_EXEMPLO`,
`object_guid=00000000-0000-0000-0000-000000000002`.

Critérios da escolha (não foi "o primeiro dos 25"): é `FUNCTION_BLOCK` (tem
corpo de lógica, não é ação nem pasta); declaração de 230 caracteres, a menor
útil entre os candidatos; usa dois `TON` e um `ESTADO_BLINK: INT` RETAIN, o
que torna uma eventual representação conferível a olho (dois temporizadores,
duas saídas booleanas); e satisfaz o critério L0 — `has_declaration=true`,
`has_implementation=false`.

## 4. `status.json` + `status-history.jsonl` (interno escreve, host lê)

Estados, em ordem de progresso:

```text
created
mastertool_started
script_started
provenance_validated
project_identity_validated
scanning
exporting
probing_ladder_dynamic_surface
probing_ladder_extender_surface
probing_plcopen_export_signature
exporting_plcopen_xml
validating
completed
failed              (terminal)
needs_interaction   (terminal)
```

`created` e `mastertool_started` são escritos pelo **host**. Do
`script_started` em diante, pelo **interno**.

Formato de `status.json`:

```json
{
  "schema_version": 1,
  "run_id": "...",
  "state": "exporting",
  "updated_at": "2026-07-24T17:31:05.123000",
  "detail": "exportando 68 objetos textuais",
  "error": null,
  "traceback": null
}
```

### Substituição de `status.json` via arquivo temporário

Procedimento obrigatório:

1. escreve `status.json.tmp`;
2. remove `status.json` se existir;
3. `os.rename("status.json.tmp", "status.json")`.

**IronPython 2.7 não tem `os.replace`** (é Python 3.3+), e no Windows o
`os.rename` falha se o destino existir. Por isso o passo 2 é necessário — e
por isso a sequência **não é atômica**: existe uma janela entre remover e
renomear em que `status.json` não existe.

Mitigação obrigatória: **`status-history.jsonl`, append-only**, uma linha
JSON por transição, gravada **antes** da troca do `status.json`. Ele é a
fonte confiável se o processo morrer na janela. Nunca truncar, nunca
reescrever.

Não usar `System.IO.File.Replace` do .NET: seria uma superfície de
dependência nova, não aprovada, para ganhar pouco frente ao log append-only.

## 5. `bootstrap.py` (host gera, MasterTool executa)

Esqueleto obrigatório — o host gera este arquivo, não um genérico:

```python
# -*- coding: utf-8 -*-
import json, os, sys

run_dir = os.path.dirname(os.path.abspath(__file__))
config_path = os.path.join(run_dir, "run-config.json")
f = open(config_path, "r")
try:
    config = json.load(f)
finally:
    f.close()

scripts_dir = config["mastertool_scripts_dir"]
if scripts_dir not in sys.path:
    sys.path.insert(0, scripts_dir)

from automation import supervised_snapshot_runner
supervised_snapshot_runner.main(run_dir, globals())
```

**O `globals()` na última linha não é opcional.** Os globais `projects` e
`system` são injetados pelo ScriptEngine **apenas no escopo do arquivo
principal executado** — ou seja, no `bootstrap.py`, não dentro dos módulos
importados. É exatamente o padrão já usado e aprovado em
`probes/15_validate_command_line_execution.py` (`main(script_globals)`) e o
motivo de `common/compatibility.probe_globals` receber o dicionário de
escopo explicitamente. Um runner que chamasse `globals()` de dentro do
próprio módulo não enxergaria `projects` e abortaria sempre.

## 6. Sequência do runner interno

```text
1. escreve status=script_started
2. valida procedência (platform/cli + IronPython + 2.7)   -> falha: failed
3. confere que run_dir derivado de __file__ == config     -> falha: failed
4. carrega e valida run-config.json (schema + operations) -> falha: failed
5. escreve status=provenance_validated
6. resolve projects.primary via common/compatibility + common/capabilities
7. compara projects.primary.path com expected_project_path (normalizado,
   case-insensitive)                                      -> falha: failed
8. confirma identidade da Application (name/guid/type_guid) -> falha: failed
9. escreve status=project_identity_validated
10. status=scanning   -> chama o scanner estrutural já aprovado
11. status=exporting  -> chama o exportador textual já aprovado
12. (opcional) inventário gráfico, se operations pedir
13. status=validating -> confere que os artefatos esperados existem e que os
    checksums fecham
14. escreve a declaração final e status=completed
```

Passos 10–12 **chamam os módulos de `common/`**. É proibido copiar código dos
probes 12/13/14 para dentro do runner: o probe e o runner passariam a ter
duas cópias que divergem silenciosamente.

### 6.1 API exata a chamar (verificada no código, não presumida)

```python
from common import project_access, file_io, checksums, safety
from common import read_only_project_scanner as scanner_mod
from common import read_only_text_exporter as exporter_mod
from common import graphic_language_inventory as inventory_mod

# projeto  (NAO usar capabilities.probe_member direto: ja existe wrapper)
project, error_msg = project_access.get_primary_project(script_globals)
path = project_access.get_project_path(project)

application = getattr(project, "active_application")

# scanner
scanner = scanner_mod.ReadOnlyProjectScanner(
    max_depth=..., max_total_nodes=..., max_children_per_node=...,
    expected_root_count=...)
scan_result = scanner.scan(project)
flat = scanner_mod.flatten_tree(scan_result["tree"])
idx  = scanner_mod.build_node_indexes(flat)

# exportador textual
exporter = exporter_mod.ReadOnlyTextExporter(
    max_depth=..., max_total_nodes=..., max_children_per_node=...,
    max_text_objects=..., max_document_characters=...,
    max_total_characters=...,
    expected_application_name=cfg["expected_application_name"],
    expected_application_type_guid=cfg["expected_application_type_guid"],
    expected_application_guid=cfg["expected_application_guid"])

export_result = exporter.export(application, output_directory=None)
written = exporter_mod.write_text_export_artifacts(export_result, run_output_dir)

# inventario grafico
engine = inventory_mod.GraphicLanguageInventory(... mesmos expected_* ...)
identity = engine.probe_application_identity(application, mismatches_out)
inv_result = engine.inventory(application)
by_state = inventory_mod.split_by_state(inventory_mod.flatten_tree(inv_result["tree"]))

# artefatos
run_output = file_io.new_export_dir(output_root, "supervised_snapshot")
file_io.write_json(os.path.join(run_output, "x.json"), data)
file_io.write_text(os.path.join(run_output, "x.md"), text)
checksums.write_checksums_file(run_output, os.path.join(run_output, "checksums.sha256"))
```

### 6.2 Identidade da Application — assimetria real entre os dois módulos

- `GraphicLanguageInventory.probe_application_identity(...)` é **pública**.
- No exportador o método equivalente é **privado**:
  `ReadOnlyTextExporter._probe_application_identity(application, mismatches_out)`.

`export()` **chama esse probe internamente e reporta** o resultado em
`export_result["application_identity_mismatch"]`, mas **não aborta**. Quem
aborta é o chamador — está escrito assim no próprio
`probes/13_validate_text_exporter.py` ("QUEM ABORTA e este script").

Portanto o runner deve **pré-checar antes de exportar**, exatamente como o
probe 13 já faz:

```python
identity_mismatches = []
application_identity = exporter._probe_application_identity(application, identity_mismatches)
if identity_mismatches:
    # status=failed, grava o motivo, NAO chama export()
```

Sim, é chamada a um membro privado. É o padrão já aprovado e em produção no
probe 13; duplicar a lógica de identidade dentro do runner seria pior.

### 6.3 Os `expected_*` vêm do config, nunca hardcoded

Os probes 13 e 14 embutem os GUIDs de `ExemploPlanta V1.0`. O runner **não pode**
fazer isso — ele precisa servir qualquer projeto. Os três valores vêm de
`run-config.json` (seção 2). Se estiverem ausentes do config, o runner
**falha** em vez de assumir um padrão.

## 7. Declaração final (interno grava em `output/run-report.json`)

```json
{
  "project_saved": false,
  "build_called": false,
  "online_operation": false,
  "download_called": false,
  "force_called": false,
  "original_project_touched": false
}
```

## 8. Critérios de aborto (todos ⇒ `failed`, nada executado depois)

- não está em IronPython/CLI;
- `projects.primary` não existe;
- projeto aberto ≠ cópia esperada;
- `run_dir` derivado ≠ `run_dir` do config;
- `output_dir` fora de `allowed_output_root`;
- artefato existente seria sobrescrito;
- config pede operação não autorizada (ou traz chave desconhecida);
- identidade da `Application` diverge;
- exceção não prevista (com `traceback` no status).

O hash de pré-condição é conferido pelo **host** antes de abrir o MasterTool
(e de novo no fim); o interno não lê o arquivo `.project`.

## 9. Divisão de responsabilidades

| Host (Python 3.11) | Interno (IronPython 2.7) |
|---|---|
| cria `run_dir`, gera `bootstrap.py` e `run-config.json` | lê `run-config.json` |
| confere a cópia descartável e calcula o hash inicial | não toca no arquivo `.project` |
| monta o comando e inicia o MasterTool com **UI visível** | executa a aquisição |
| aguarda o processo, captura código de saída e duração | escreve `status.json` + histórico |
| verifica processo órfão | — |
| confere o hash final da cópia | — |
| valida os artefatos produzidos | grava a declaração final |
| executa o indexador Python 3 | — |
| produz o relatório consolidado | — |

O host **nunca** mata processo do MasterTool. Se exceder o timeout sem o
status avançar, marca `needs_interaction` e devolve o controle ao operador —
provavelmente há um diálogo aberto na tela esperando decisão humana.

## 9.0 VALIDAÇÃO OPERACIONAL — Etapa B aprovada (2026-07-24 21:21)

Execução supervisionada real, run `2026-07-24_21-21-01`, contra a mesma cópia
descartável validada no t4 da Etapa A. **Um único comando** substituiu abrir o
MasterTool, rodar vários scripts à mão, localizar artefatos e disparar o
indexador.

Máquina de estados completa, em ~4 s de trabalho efetivo:

```text
script_started -> provenance_validated -> project_identity_validated
-> scanning -> exporting -> validating -> completed
```

**Aquisição — bate exatamente com a baseline `v0.1.0`:**

| Métrica | Baseline | Run 21:21 |
|---|---|---|
| Nós do scanner | 117 | 117 |
| Nós da Application | 92 | 92 |
| Objetos textuais | 68 | 68 |
| Caracteres | 66.360 | 66.360 |
| Erros de scanner / export | 0 / 0 | 0 / 0 |
| Checksums | — | 155 OK, 0 falhas |

**Índice (`StaticProjectIndexer`) — bate exatamente:**

| Métrica | Baseline | Run 21:21 |
|---|---|---|
| Símbolos | 60 | 60 |
| Tipos | 8 | 8 |
| Referências `resolved` | 409 | 409 |
| `partially_resolved` | 64 | 64 |
| `unresolved` | 61 | 61 |
| Chamadas | 12 | 12 |
| EntradasExemplo read-write | 522 | 522 (468 + 54 `_unresolved`) |

Diagnósticos: `diagnostics.json` 65 (1 info + 64 warning heurísticos, **0
erros**), `resolution-diagnostics.json` 134 info, **0 erros**.

**Segurança:** declaração final com as 6 chaves em `false`
(`project_saved`, `build_called`, `online_operation`, `download_called`,
`force_called`, `original_project_touched`); SHA256 da cópia descartável
**idêntico antes e depois**
(`E278D1C270DA28FA5F25D6A8EE7FED403988BBAD0D759D762A973B4A4E688C4E`);
projeto original intocado.

`objects_with_implementation: 68→14` casa com os `supported: 14` da Fase L0 —
dois caminhos independentes chegando ao mesmo número.

### Quatro defeitos que só a execução real revelou

Nenhum deles era detectável por teste em CPython; todos moram em fronteiras
que a suíte não cruza.

1. **Procedência reinventada com `AND`** em vez de reusar
   `compatibility.is_ironpython()` (que usa `OU`). Neste host `sys.version`
   devolve banner do produto sem a palavra "IronPython" — reprovava sempre.
2. **Linha de comando como lista.** `subprocess.list2cmdline` cita o token
   inteiro quando há espaço (`"--project=C:\...\Pasta Com Espacos\..."`),
   e o MT8500 **ignora a flag em silêncio** — abriu sem projeto, sem erro. O
   `--runscript` sobreviveu por acidente (caminho do run sem espaço).
3. **Export não indexável**: faltavam `manifest.json` e `flat-objects.json`,
   e o host tratava o índice ausente como `ok=True` — um passo pedido que não
   ocorreu se apresentando como sucesso.
4. **Runner invisível na UI**: zero `print()`, diferente de todos os probes.
   Com a UI visível — cujo único propósito é supervisão humana — a aba de
   Mensagens ficava vazia, indistinguível de travamento. Pior: a aquisição
   terminava em 4 s e o host ficava bloqueado esperando o operador **fechar o
   MasterTool**, sem nada na tela dizendo que a próxima ação era dele.

O item 4 é o mais instrutivo: os três primeiros quebravam a execução, e esse
quebrava a *supervisão*, que é o motivo de a Etapa B existir com UI visível.

## 9.1 Estado da implementação e limitações conhecidas (2026-07-24)

Os dois lados foram implementados em paralelo, por agentes diferentes, sem
se verem — só este contrato os liga. A integração foi verificada de fato: o
`run-config.json` **gerado pelo host** foi entregue ao
`run_config.load_run_config()` **do lado interno**, que o aceitou, e os
limites resolvidos bateram com os validados da baseline `v0.1.0`. Contrato
escrito não é contrato cumprido; esse cruzamento é o que prova.

Duas limitações reais, nenhuma bloqueante para a primeira execução:

**1. `inventory_graphic_objects` tem default `false` no host.** O exemplo da
seção 2 mostra `true`, mas `RunOperations.inventory_graphic_objects` nasce
`False`. Para a primeira validação da Etapa B isso é indiferente — os
números alvo (117 nós, 92 da Application, 68 objetos textuais, 66.360
caracteres) vêm do scanner e do exportador. Mas a **Fase L1 vai precisar do
inventário ligado**, e quem montar aquela execução precisa passar
`inventory_graphic_objects=True` explicitamente.

**2. O host não emite a seção `limits`.** `RunConfig` não tem esse campo,
então o `run-config.json` gerado nunca traz `limits` e o lado interno sempre
aplica os defaults. Como os defaults **são** os valores validados, o
comportamento está correto e a baseline é reproduzível. A consequência é que
o caminho de configuração de limites existe e é validado no lado interno,
mas hoje só é alcançável editando o `run-config.json` à mão. Se em algum
momento for preciso apertar ou afrouxar limites por execução, o campo tem que
subir para o `RunConfig` do host.

## 10. Fora de escopo (Etapa B)

`--noUI`; encerramento forçado; resposta automática a diálogo; build; save;
login; download; force; escrita no projeto; interpretação Ladder (L1);
lote de vários projetos; serviço persistente; watch de diretório.

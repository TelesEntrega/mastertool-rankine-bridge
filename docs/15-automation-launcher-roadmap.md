# Automação — comando único de aquisição (snapshot → índice → MCP)

> Estado: **registrado em 2026-07-24, Etapa A em preparação**. Objetivo:
> substituir a execução manual (`00_smoke_test.py` → probe 12 → probe 13 →
> `build_static_index` → `ProjectIndex`/MCP) por um único comando Windows
> (`mastertool-bridge snapshot --project ... --output ...`).
>
> **Regra permanente desta trilha, reafirmada explicitamente pelo usuário**:
> nenhuma etapa além de A (prova mínima e inofensiva) pode ser construída
> sobre suposição — as flags de linha de comando do CODESYS
> (`--project`/`--runscript`/`--scriptargs`/`--noUI`) estão documentadas
> publicamente para a plataforma CODESYS em geral, mas **ainda não foram
> confirmadas no `MT8500.exe` 3.63 real da Altus**. A Etapa A existe
> exatamente para provar isso, com um script inofensivo, ANTES de qualquer
> launcher definitivo.
>
> **Quem executa a Etapa A**: o usuário, não o agente. O primeiro teste
> deve rodar com a interface VISÍVEL (sem `--noUI`), justamente para um
> humano observar e poder intervir em diálogos inesperados (licença,
> conversão, biblioteca ausente) — supervisão visual que um agente não tem
> como fazer. Mesmo padrão já seguido em toda execução real dentro do
> MasterTool até aqui (scripts preparados pelo agente, executados e
> observados pelo usuário).

## Fluxo automático pretendido

```text
mastertool-bridge snapshot --project "C:\Projetos\Projeto.project"
        ↓
cria cópia descartável do projeto
        ↓
abre MT8500.exe automaticamente
        ↓
executa um script orquestrador IronPython
        ↓
scanner + exportador + inventário Ladder
        ↓
fecha o MasterTool
        ↓
valida manifests e checksums
        ↓
executa o StaticProjectIndexer
        ↓
publica o índice para API Python e MCP
```

## Comando de baixo nível a ser provado (hipótese, NÃO confirmada)

```powershell
"C:\Program Files (x86)\Altus\MT8500 3.63\MT8500.exe" `
  --project="C:\Projetos\Projeto.project" `
  --runscript="C:\mastertool-ai-bridge\scripts\mastertool\automation\run_snapshot.py" `
  --scriptargs:'--output "C:\ProjetosIndexados\ProjetoA"' `
  --noUI
```

> Etapa A usa hoje `scripts/mastertool/probes/15_validate_command_line_execution.py`
> (fora de `scripts/mastertool/automation/`, na sequencia numerada de probes —
> o numero 14 ja estava ocupado por `probes/14_inventory_graphic_pous.py`).
> `run_snapshot.py` acima e o alvo hipotetico da Etapa B, ainda nao criado.

`--project`/`--runscript`/`--scriptargs`/`--noUI` são documentados pela
plataforma CODESYS em geral, não confirmados especificamente no `MT8500.exe`
3.63 da Altus. Documentação pública da Altus encontrada demonstra só a
execução manual via **Ferramentas → Scripting → Executar Arquivo de
Script** — não confirma as opções de linha de comando neste executável
customizado.

## Etapas de implantação (gated, cada uma só avança com a anterior provada)

### Etapa A — prova de linha de comando (`test: validate MasterTool command-line script execution`)

Script mínimo e inofensivo, que só grava evidência de execução (nunca lê/
escreve nada do projeto): `script_started`, `argv` cru, versão do
IronPython, contexto de execução (cwd, `__file__`, se disponível). Testar
NESTA ORDEM, um de cada vez, com a UI visível (sem `--noUI`):

1. `--runscript` sozinho;
2. `--scriptargs`;
3. `--project`;
4. combinação `--project` + `--runscript`;
5. só depois, `--noUI`.

**Executado pelo usuário.** Script preparado nesta fatia; ver "Estado de
execução" ao final.

### Etapa B — runner automático (`feat: add unattended MasterTool snapshot runner`)

`scripts/mastertool/automation/run_snapshot.py` — substitui a execução
manual dos probes, reaproveitando diretamente os módulos `common/` já
aprovados (scanner, exportador, inventário gráfico). Argumentos:
`--output`/`--run-id`/`--mode snapshot`/`--expected-project-hash`.
**Bloqueada até a Etapa A confirmar quais flags realmente funcionam** —
construir antes disso seria arquitetura baseada em suposição.

### Etapa C — launcher externo (`feat: add host launcher for MasterTool snapshots`)

`src/mastertool_bridge/launcher/` (Python 3.11): localizar `MT8500.exe`,
criar cópia descartável do `.project`, montar argumentos com escaping
correto, iniciar processo, capturar stdout/stderr, timeout, código de
saída, detecção de encerramento anormal, impedir aquisições simultâneas,
validar artefato produzido, disparar o indexador externo. **Bloqueada até
a Etapa B existir e ter sido validada.**

### Etapa D — pipeline completo (`feat: add end-to-end automatic project snapshot pipeline`)

Comando único `mastertool-bridge snapshot --project ... --output ...`,
modos `--interactive`/`--headless`/`--keep-copy`/`--no-index`/
`--index-only`. **Bloqueada até a Etapa C existir e ter sido validada.**

## Cuidados obrigatórios (todas as etapas, sem exceção)

* nunca usar `--noUI` antes de confirmar, com UI visível, que nenhum
  diálogo de conversão/licença/biblioteca aparece — CODESYS documenta que,
  sem `--textPrompts`, prompts podem ser respondidos automaticamente com
  valores padrão em modo sem interface, o que é inaceitável sem prova
  prévia;
* sempre abrir uma CÓPIA do projeto, nunca o original;
* nunca salvar sobre o original;
* rejeitar projetos que peçam conversão automática;
* nenhum build, login, download ou force;
* retornar `needs_interaction` explícito se houver senha/licença/biblioteca
  ausente/diálogo inesperado — nunca tentar "resolver" silenciosamente;
* produzir log mesmo quando o MasterTool falhar;
* matar SOMENTE o processo que o próprio launcher iniciou, nunca outra
  sessão do usuário.

## Prova de procedência (critério objetivo, adicionado 2026-07-24)

Um artefato só pode ser aceito como **gerado dentro do MasterTool** se, no
`result.json`, valerem as três condições:

```text
runtime.platform        == "cli"
runtime.runtime_family  == "IronPython"
runtime.version_info    começa com [2, 7]
```

**Por que isso existe.** Em 2026-07-24 14:57 uma execução do probe 14 foi
inicialmente confundida com uma execução dentro do MasterTool. A análise
forense (registrada em
`workspace/exports/2026-07-24_14-57-40_14_inventory_graphic_pous/INVALID-RUN.md`)
mostrou que ela rodou em **CPython 3, fora do MasterTool**, provado por duas
impressões digitais independentes e verificáveis relendo os arquivos:

1. **Espaço em branco à direita no JSON** — o `json.dumps(indent=…)` do
   Python 2 deixa espaço após a vírgula no fim da linha; o Python 3.4+ não.
   A execução suspeita tinha 0 linhas assim; todas as execuções reais
   conhecidas dentro do MasterTool têm milhares.
2. **Resolução do timestamp** — sob IronPython o horário vem do
   `DateTime.Now` do .NET, com resolução de milissegundo (`.599000`); o
   CPython dá microssegundos reais (`.688896`).

Sem esse critério, um `--runscript` que silenciosamente **não** executasse
dentro do MasterTool poderia ser lido como sucesso — exatamente o erro que a
Etapa A precisa não cometer. O critério está implementado em
`src/mastertool_bridge/automation/cli_probe_verify.py` (`check_provenance`),
aplicado a todos os testes que produzem artefato.

## Etapa A — runbook de execução (5 testes, nesta ordem)

### Ambiente confirmado (verificado em 2026-07-24, não presumido)

```text
Executável : C:\Program Files (x86)\Altus\MT8500 3.63\MT8500\Common\MT8500.exe
FileVersion: 3.63.300.00
Probe      : scripts\mastertool\probes\15_validate_command_line_execution.py
Saída      : workspace\logs\cli-probe\<t1|t2|t3|t4|t5>\
```

A raiz do repositório contém espaços (`Pasta Com Espacos`), então **todo
caminho passado já é, por construção, um teste real de preservação de aspas**
— não é preciso inventar um caminho artificial com espaço.

### Auxiliar de host

`scripts/host/run_cli_probe_test.ps1` monta o comando, valida as
pré-condições e captura o que o probe IronPython **não consegue ver de
dentro**: código de saída, duração, processo órfão e hash da cópia
descartável antes/depois.

**Fail-closed por padrão: sem `-Execute` ele não lança nada.** Rode primeiro
sem a flag (ensaio), confira o comando impresso, e só então repita com
`-Execute`.

Pré-condições que ele bloqueia sozinho:

- `MT8500.exe` inexistente no caminho informado;
- probe ausente;
- **qualquer instância do MasterTool já aberta** — uma instância existente
  pode absorver o `--runscript` ou encerrar o processo novo na hora,
  falseando o resultado. Feche o MasterTool antes de cada teste;
- `-ProjectCopy` apontando para o projeto **original** (t3/t4/t5).

Ele **nunca** mata processo — se sobrar órfão, só reporta.

### Preparar a cópia descartável (antes do t3)

```powershell
$orig = 'C:\caminho\para\Projeto Teste\ExemploPlanta V1.0.project'
$dest = 'C:\caminho\para\Projeto Teste\_descartavel\ExemploPlanta V1.0 COPIA.project'
New-Item -ItemType Directory -Force -Path (Split-Path $dest) | Out-Null
Copy-Item -LiteralPath $orig -Destination $dest
(Get-FileHash -LiteralPath $dest -Algorithm SHA256).Hash
```

### Os 5 testes

Em todos: `cd` para `mastertool-ai-bridge\scripts\host` primeiro. Ensaio sem
`-Execute`, depois com.

| # | Comando | O que prova |
|---|---|---|
| t1 | `.\run_cli_probe_test.ps1 -Test t1 -Execute` | `--runscript` sozinho dispara o script dentro do MasterTool |
| t2 | `.\run_cli_probe_test.ps1 -Test t2 -Execute` | `--scriptargs` chega ao script com aspas/espaços preservados |
| t3 | `.\run_cli_probe_test.ps1 -Test t3 -ProjectCopy '<cópia>' -Execute` | `--project` abre o projeto certo, sem diálogo e sem modificar |
| t4 | `.\run_cli_probe_test.ps1 -Test t4 -ProjectCopy '<cópia>' -Execute` | combinação: script roda **no contexto do projeto** |
| t5 | `.\run_cli_probe_test.ps1 -Test t5 -ProjectCopy '<cópia>' -Execute` | `--noUI` — **só depois de t1..t4 aprovados** |

**t1 e t2 — `projects` indisponível é esperado, não é falha.** Sem
`--project` não há projeto aberto, então `globals.projects_available: false`
é o resultado correto. O verificador registra isso como observação e nunca
reprova o teste por esse motivo.

**t3 não produz `result.json`** (nenhum script é passado). A evidência dele é
necessariamente manual: projeto correto aberto na tela, ausência de diálogo
de conversão/licença/biblioteca, e hash da cópia idêntico antes/depois. O
verificador marca t3 como `manual` e **nunca** o aprova sozinho.

**Durante t1–t4, a UI fica visível.** Se aparecer diálogo de licença,
conversão ou biblioteca ausente: **cancele** e anote o que apareceu. Isso não
é ruído — é o resultado do teste.

### O que anotar manualmente

O script grava `host-observation.json` (dados objetivos). O que só você vê
vai em `observation.md`, no mesmo diretório do teste: diálogos que
apareceram, demora anormal, janela inesperada, se a UI abriu de fato, se o
projeto exibido era o correto.

### Fechar o gate

```powershell
python -m mastertool_bridge verify-cli-probe --results-dir workspace\logs\cli-probe --output workspace\logs\cli-probe\gate-report.json
```

O relatório traz as 5 chaves de decisão exigidas — `runscript_supported`,
`scriptargs_supported`, `project_supported`, `combined_execution_supported`,
`headless_status` — mais `gate_b_unblocked`.

**`headless_status` não bloqueia a Etapa B.** Se `--noUI` for inseguro ou
inconsistente, o primeiro runner opera com UI visível e supervisão humana;
`gate_b_unblocked` depende apenas de t1/t2/t3/t4.

## Resultados reais dos testes (registro vivo)

### t1 — `--runscript` sozinho: **APROVADO** (2026-07-24 16:21)

`--runscript` **funciona** no `MT8500.exe` 3.63.300.00. Procedência confirmada
no artefato (`workspace/logs/cli-probe/t1/collected/result.json`):
`platform="cli"`, `runtime_family="IronPython"`,
`version_info=[2, 7, 12, "final", 0]`, `script_started=true`.

Observação de host: `exit_code=0`, duração 152,4 s (inclui o tempo até o
operador fechar a UI), **zero processo órfão**, nenhum diálogo de
licença/conversão/biblioteca.

Três achados que mudam o desenho das etapas seguintes:

**1. `sys.argv` traz apenas o caminho do script.** Sem `--scriptargs`, o
`argv` é uma lista de um elemento só (o próprio `.py`). Nenhum argumento
extra é injetado pelo MT8500.

**2. `projects`/`projects.primary` existem MESMO SEM projeto aberto.** Com
`--runscript` sozinho, o probe registrou `projects_available=true` e
`primary_available=true`, mas `project.path=null`. Consequência direta para
o gate: **`project.path` é o único discriminador confiável de "há projeto
aberto"** — a presença de `projects.primary` não prova nada. O verificador
checa os três campos em t4, mas o peso da prova está em `path`.

**3. O `cwd` do processo é o do chamador (`C:\WINDOWS\system32`), não o do
repositório.** Por isso a camada 3 de `_resolve_output_dir` (gravar em
`os.getcwd()`) tentaria escrever dentro de `system32` — o que falharia por
permissão e cairia no `print()`. A camada 2 (relativa a `__file__`) é a que
realmente sustenta o t1, e funcionou.

**Consequência operacional**: em t1 não há `--output`, então o artefato NÃO
cai em `workspace/logs/cli-probe/t1/` e sim na camada 2
(`workspace/logs/<timestamp>_validate_command_line_execution/`). O wrapper
foi corrigido depois desta execução para varrer as 3 camadas, filtrar por
data e copiar o achado para `<outDir>/collected/` (o original nunca é movido
nem apagado). A coleta do t1 foi feita manualmente e está registrada em
`workspace/logs/cli-probe/t1/collected/COLLECTION-NOTE.md`.

### t2 — `--scriptargs`: **APROVADO, com uma restrição dura** (2026-07-24 16:33 e 16:36)

`--scriptargs` **é suportado** e os argumentos chegam como elementos de
`sys.argv`. Mas o MT8500 3.63 **quebra o valor em espaços em branco**, e as
aspas não sobrevivem.

Duas execuções, uma variável trocada entre elas:

**16:33 — saída em caminho COM espaços** (`...\Pasta Com Espacos\...\cli-probe\t2`):

```text
argv[0] '...\Pasta Com Espacos\...\15_validate_command_line_execution.py'
argv[1] '--output=C:\caminho\para\Documents\exemplo\Pasta'
argv[2] 'IA'
argv[3] 'MasterTool\mastertool-ai-bridge\workspace\logs\cli-probe\t2'
```

**16:36 — saída em caminho SEM espaços** (`C:\mastertool-cli-probe\t2`):

```text
argv[0] '...\Pasta Com Espacos\...\15_validate_command_line_execution.py'
argv[1] '--output=C:\mastertool-cli-probe\t2'
```

**A assimetria é o achado central**: o caminho do `--runscript` (`argv[0]`)
chegou **intacto, com espaços**, nas duas execuções. Só o valor do
`--scriptargs` foi tokenizado. Ou seja, o MT8500 trata os dois de formas
diferentes, e não há aspas que resolvam pelo lado do chamador — testamos
`--scriptargs:"..."` e o valor foi partido mesmo assim.

**Efeito colateral da execução com espaços**: a camada 1 do probe "teve
sucesso" gravando no caminho truncado e **criou o diretório**
`C:\caminho\para\Documents\exemplo\Pasta\`, fora do
repositório. Artefatos preservados em
`workspace/logs/cli-probe/_evidencia-execucao-com-espacos/`.

**Consequência de projeto para a Etapa B (não negociável)**: nenhum caminho
passado por `--scriptargs` pode conter espaço. Duas saídas possíveis, a
decidir na Etapa B:

1. usar um diretório de trabalho sem espaços (ex.: `C:\mastertool-cli-probe`);
2. não passar caminho por argumento — o runner lê um arquivo de configuração
   cujo caminho, esse sim, vai pelo `--runscript` (que preserva espaços).

O runner de host já aplica a opção 1: em t2/t4/t5 ele detecta espaço no
diretório de saída, troca automaticamente para `C:\mastertool-cli-probe\<teste>`
e registra a troca em `host-observation.json` (`output_dir_auto_switched`).
Se ainda restar espaço, ele bloqueia em vez de gravar no lugar errado.

### t3 — `--project` sozinho: **APROVADO** (2026-07-24 16:39–16:43)

Projeto correto aberto (título `ExemploPlanta V1.0 COPIA.project`, árvore de
Dispositivos completa), **nenhum diálogo** de conversão, licença ou
biblioteca. `exit_code=0`, zero órfãos, e o SHA256 da cópia descartável
**idêntico antes e depois**
(`E278D1C270DA28FA5F25D6A8EE7FED403988BBAD0D759D762A973B4A4E688C4E`) — o
`--project` não modificou o arquivo. Nenhum `result.json`, como esperado
(sem `--runscript`). Detalhes e procedência de cada afirmação em
`workspace/logs/cli-probe/t3/observation.md`.

**Ressalva registrada, não descartada**: apareceu 1 advertência
**não-modal** na categoria Devices —
`Device description for '<vazio>' is missing`
(`[Device: Configuration: NX30...]`). Origem **indeterminada**: não é
possível decidir offline se é pré-existente do projeto ou consequência do
`--project`, porque o `ReadOnlyTextExporter` é escopado à `Application` e
nunca percorre o ramo Device/Configuration. Como não é diálogo, não reprova
o item `no_conversion_or_license_dialog`. **Mas é item de atenção específico
do t5**: sem `--textPrompts`, o CODESYS documenta que prompts podem ser
respondidos automaticamente com valor padrão em modo sem interface, e uma
descrição de dispositivo ausente é exatamente o tipo de condição que pode
virar prompt silencioso. Controle que resolveria (uma execução, ainda não
feita): abrir a mesma cópia pela UI e ver se a advertência reaparece.

### t4 — `--project` + `--runscript` + `--scriptargs`: **APROVADO** (2026-07-24 16:48)

A combinação funciona. Linha de comando efetiva:

```text
--project="...\_descartavel\ExemploPlanta V1.0 COPIA.project"
--runscript="...\Pasta Com Espacos\...\15_validate_command_line_execution.py"
--scriptargs:"--output=C:\mastertool-cli-probe\t4"
```

Note que `--project` e `--runscript` carregam caminhos **com espaços** sem
problema; só o `--scriptargs` precisou do caminho sem espaços (achado do t2).

Resultado (`workspace/logs/cli-probe/t4/collected/result.json`):

- procedência `cli` / `IronPython` / `[2, 7, 12]`;
- `argv` com 2 elementos, `--output=C:\mastertool-cli-probe\t4` íntegro;
- **`project.path` = exatamente o caminho da cópia descartável** — este é o
  campo que prova o contexto. `projects_available`/`primary_available` vêm
  `True` mesmo sem projeto (achado do t1), então sozinhos não provariam nada;
- as 4 flags de `safety` em `false`, e `safety_declaration` inteira
  fail-closed (`read_only=true`, sem navegação, sem leitura de conteúdo, sem
  compilação, sem acesso online);
- `exit_code=0`, zero órfãos, hash da cópia **inalterado**.

### Gate da Etapa A: **ABERTO** (`gate_b_unblocked: True`)

```text
runscript_supported:          True
scriptargs_supported:         True
project_supported:            confirmed
combined_execution_supported: True
headless_status:              not_tested   (não bloqueia, por decisão do usuário)
gate_b_unblocked:             True
```

Reproduzível com:

```powershell
python -m mastertool_bridge verify-cli-probe `
  --results-dir workspace\logs\cli-probe `
  --expected workspace\logs\cli-probe\expected.json
```

### t5 — `--noUI`: não executado

Opcional: `headless_status` não bloqueia a Etapa B. Se `--noUI` for inseguro
ou inconsistente, o primeiro runner opera com UI visível e supervisão humana.
Atenção específica ao rodar: a advertência de device description do t3 pode
virar prompt respondido automaticamente neste modo.

## Estado de execução (registro vivo)

**Etapa A**: código concluído e commitado (`a4180c1`,
`test: add safe MasterTool command-line execution probe`) em
`scripts/mastertool/probes/15_validate_command_line_execution.py` +
`tests/unit/test_validate_command_line_execution.py` (24 testes). Saída
(`result.json`) segue o schema exato: `schema_version` (int `1`),
`script_started`, `argv`, `runtime{platform,version,version_info}`,
`globals{projects_available,system_available}`,
`project{primary_available,path}` (lê `projects.primary.path` com
segurança, reaproveitando a capacidade já aprovada desde
`00_smoke_test.py`/`probes/03_project_navigation.py` — não é API nova),
`safety{project_modified,save_called,build_called,online_operation}`.
`observation.md`/`summary.md` são preenchidos MANUALMENTE pelo usuário,
o script nunca os cria. Nota prática: `--output <dir>` grava dentro de um
subdiretório com timestamp (`<dir>/<timestamp>_validate_command_line_execution/result.json`),
nunca direto em `<dir>/result.json` — mesma disciplina anti-sobrescrita
usada em todos os probes.

**Não executado dentro do MasterTool real** — aguardando o usuário rodar
os 5 testes ordenados (seção "Etapa A" acima), com a UI visível, dentro
do `MT8500.exe` 3.63 real. Este documento será atualizado com o
resultado assim que existir — esse resultado é o próprio gate que libera
(ou não) a Etapa B.

**Etapas B/C/D**: não iniciadas — dependem do resultado real da Etapa A.

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
C:\mastertool-ai-bridge-runs\<run-id>\
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

  "repo_root": "C:\\...\\mastertool-ai-bridge",
  "mastertool_scripts_dir": "C:\\...\\mastertool-ai-bridge\\scripts\\mastertool",

  "expected_project_path": "C:\\...\\_descartavel\\ExemploPlanta V1.0 COPIA.project",
  "expected_project_sha256": "E278D1C2...688C4E",

  "expected_application_name": "Application",
  "expected_application_guid": "00000000-0000-0000-0000-000000000001",
  "expected_application_type_guid": "639b491f-5557-464c-af91-1471bac9f549",

  "run_dir": "C:\\mastertool-ai-bridge-runs\\2026-07-24_17-30-00",
  "output_dir": "C:\\mastertool-ai-bridge-runs\\2026-07-24_17-30-00\\output",
  "allowed_output_root": "C:\\mastertool-ai-bridge-runs",

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

### Escrita "atômica" — e por que ela não é atômica de verdade

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

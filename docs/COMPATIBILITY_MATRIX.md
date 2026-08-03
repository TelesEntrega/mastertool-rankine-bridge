# Matriz de compatibilidade

> **NORMATIVO E VIGENTE.** Complementa [`CAPABILITY_MATRIX.md`](CAPABILITY_MATRIX.md):
> aquele documento diz **o que** foi provado; este diz **em qual produto e
> versão**. Fonte canônica do estado vigente: [`CURRENT_STATUS.md`](CURRENT_STATUS.md).
> Roadmap normativo: [`ROADMAP.md`](ROADMAP.md). Modelo de segurança:
> [`SAFETY_MODEL.md`](SAFETY_MODEL.md).

## 0. Regra de leitura

```text
qualificado       validado com evidência repetida e critério explícito
exercido uma vez  rodou contra o produto real, uma execução, sem repetição
não medido        nunca foi tentado contra este produto/versão
não aplicável     a capacidade não existe neste produto por desenho
```

`não medido` é resposta correta, não lacuna de trabalho — omitir a célula
seria pior que preenchê-la com `não medido`, porque um branco convida a
inferência.

## 1. Produtos e versões exercidos

| Produto | Versão | Executável | Runtime IronPython | Assemblies de scripting | Núcleo CODESYS |
|---|---|---|---|---|---|
| MasterTool IEC XE | 3.63 | `MT8500.exe` | 2.7.12 (banner sem versão de produto) | `ScriptEngine.plugin` etc., **4.1.0.0** | não medido nesta trilha |
| MasterTool IEC XE | 3.70 | `MT8500.exe` | 2.7.12 (banner **com** versão de produto — mudança medida, `docs/26`) | `ScriptEngine.plugin` etc., **4.1.0.0** — byte a byte idêntico ao 3.63 nas 15 sementes usadas (`docs/26`) | não medido nesta trilha |
| MasterTool X (MT9000) | 4.1.0.11 | **`MT9000.exe`** (não é `MT8500.exe`) | 2.7.12 (idêntico ao 3.70) | `ScriptEngine.plugin` etc., **4.2.0.0** — mudança de versão real, aditiva (`docs/27` §3,§6) | `3.5.18.60` (medido, `docs/27` §9, assemblies carregados) |

<caption>

**Como ler:** a designação "X4.1" foi confirmada por medição do executável
(`FileVersion`/`ProductVersion` `4.1.0.11`), não presumida do atalho ou do
nome do diretório (`docs/27` §1). Há **duas** instalações de MasterTool X
nesta máquina (4.0.0 e 4.1.0); todo artefato desta trilha registra qual
instalação produziu — o módulo do processo confirmou 4.1.0 (`docs/27` §9).

</caption>

### Aviso explícito sobre `MT8500.exe`

**`docs/15`, `docs/22` e `docs/23` invocam `MT8500.exe` na linha de comando
documentada.** Nenhuma delas vale como está para MasterTool X: o executável
mudou de nome (`MT9000.exe`), e `docs/27` §8 item 8 registra isso
explicitamente como risco. A sintaxe da linha de comando (`--runscript=`,
`--scriptargs:`, `--project=`) foi **remedida e confirmada idêntica** no
MasterTool X (`docs/27` §9), mas o nome do executável dentro de qualquer
script de invocação (`scripts/host/run_cli_probe_test.ps1`, que procura
processo por `MT8500*` — `CURRENT_STATUS.md` §4) precisa ser corrigido antes
de reutilizar esses três documentos contra MasterTool X.

### Escopo exato de "a API não mudou entre 3.63 e 3.70"

`docs/26` mediu, por reflection somente-metadados: assemblies de scripting
idênticos (`4.1.0.0` nas duas versões), catálogo estático das sementes usadas
**byte a byte idêntico**, `ScriptDriverDeviceObject` com os mesmos 859
membros públicos nas duas versões. **Essa conclusão vale só para 3.63 × 3.70
e NÃO se estende ao MasterTool X (`docs/27`).** A própria `docs/27` §3 registra
que essa suposição falharia se aplicada ao MasterTool X: os assemblies de
scripting subiram de `4.1.0.0` para `4.2.0.0` — mudança de versão real, ainda
que aditiva nas 15 sementes usadas (141 × 140 membros, uma sobrecarga a mais,
nada removido nem com assinatura alterada). Tratar "API não mudou" como regra
geral do produto, em vez de um achado específico de par de versões, seria a
inferência que este projeto não faz.

## 2. Matriz produto × capacidade

| Capacidade | MasterTool IEC XE 3.63 | MasterTool IEC XE 3.70 | MasterTool X (MT9000) 4.1.0.11 |
|---|---|---|---|
| Leitura (tree scan + export textual) | **qualificado** — `docs/11` (117 nós, 8/8), `docs/12` (92 nós, 158/158), projeto real `ExemploPlanta V1.0.project` | não medido diretamente — herdado por `docs/26` (API idêntica a 3.63 nas sementes de leitura) | **exercido uma vez** — `docs/27` §9 (probe 21, 3 raízes/34 nós, 0 erros, cópia descartável) |
| Export PLCopen (Ladder) | **qualificado** — `docs/17` (42 elementos), `docs/23` (35/35 dispositivos) | não medido diretamente — herdado por `docs/26` | **não medido** — `docs/27` §"O que continua sem medição" registra explicitamente: "Export mínimo no MasterTool X: não executado — a cópia é um projeto vazio, sem POU gráfica para exportar" |
| Inventário de dispositivo | **qualificado** — `docs/25` (35/35, 1894 parâmetros) | herdado por `docs/26` (repositório é por versão instalada, não por API) — **não medido** como inventário completo em 3.70 | **não medido** |
| Autoria ST (criar/editar DUT, GVL, FUNCTION, FUNCTION_BLOCK, PROGRAM, task, program call) | **não aplicável** — a trilha de autoria nunca rodou contra IEC XE; `create_program`/`create_function`/`create_function_block` são API **nova** medida só no MasterTool X (`docs/27` §7, marcadas `NOVO`) | **não aplicável**, mesma razão | **field_proven** (teto atual da escala, `ROADMAP.md` §2) — `docs/33`, `docs/34`, `docs/37`, `docs/39`, `docs/41`, `docs/43`, `docs/46`, `docs/47`, `docs/48`, `docs/49` |
| Build (compilação offline) | não medido nesta trilha | não medido nesta trilha | **field_proven** — `docs/37` (run-019), `docs/39` (run-021), `docs/41` (run-026), e as fábricas W6-W9 |
| Propriedades de task (`kind_of_task`, `interval`, `interval_unit`, `priority`) | não aplicável — mecanismo de escrita de propriedade só existe na trilha MasterTool X | não aplicável | **field_proven** — `docs/49` (run-037) |

<caption>

**Como ler:** "não aplicável" nesta tabela significa que a capacidade nunca
foi tentada contra aquele produto porque a trilha de autoria **começou** no
MasterTool X — não que o produto seja incapaz. Confundir os dois seria
declarar mais do que foi medido.

</caption>

## 3. Template Profiles

O Template Profile substitui o baseline posicional (`ROADMAP.md` §2.2,
`CURRENT_STATUS.md` §3): identidade de árvore por hash e por `sha256` do
arquivo, nunca por índice de posição.

### Base corrente

```text
arquivo    TemplateExemplo v1.project
sha256     596625796e4efd54d3cc2d6286e858b683f0f58de66ab9a36eed532dd1d815f5
tamanho    503.040 bytes
classe     projeto sintético com controlador NX3008 e cartões de I/O
           configurados
trocado    2026-07-31 (o usuário acrescentou os cartões de I/O e determinou
           que este arquivo passa a ser a base)
```

### Baseline anterior — INVALIDADA

```text
arquivo            cópia de "TemplateExemplo v1" sem cartões de I/O
sha256             6183d01dcae9091a531a698afe794a3cbbf8f7882c921a67aeecfa9db5540dd3
tamanho             287.152 bytes
3 raízes            34 nós
structure_sha256    b2825550…
node_path           root/1/0/0   <- o mais crítico
```

**Toda identidade posicional desta base anterior está invalidada** — contagem
de nós, `structure_sha256` e `node_path`. `node_path` é caminho de **índices**:
um cartão a mais sob o `Device` desloca o índice, e `root/1/0/0` deixa de
apontar para o `Application` (`ROADMAP.md` §2.2, `CURRENT_STATUS.md` §3).

**`CURRENT_STATUS.md` §3 declara esta pendência como aberta**: "varredura
read-only com `probes/21` sobre a base nova e recongelamento dos números como
Template Profile (fase R0b)". Este documento segue essa declaração como
autoritativa.

### Achado que precisa de decisão humana — número diferente já medido sobre a base nova

`docs/36` (`run-010`/`run-011`, ambas read-only) **já mediu** a árvore da
mesma base nova (`TemplateExemplo v1.project`, mesmo sha256 596625…815f5) e registrou:

```text
3 raízes, 42 nós (não 34)
persistent_tree_sha256  162d4fd747532bc0d9a6f22dc12eeaabcf59397ec4210e6787f68f1edf89f647
Application             root/1/0/0  (match único, resolvido por busca)
```

Isso **não** é o mesmo número que a "baseline invalidada" acima (34 nós),
porque são arquivos diferentes: 34 nós é da base **anterior** (sem I/O),
42 nós é da base **nova** (com I/O) — os dois números coexistem sem
contradição, cada um preso ao seu próprio sha256.

O que **é** uma tensão a resolver: `docs/36` concluiu que `TemplateExemplo v1.project`
estava **medido e NÃO elegível para autoria** (dois bloqueadores:
`compiler_version_unresolved` e `libraries_unresolved`), mas as execuções
posteriores W6-W9 (`docs/46` a `docs/49`) rodaram — e passaram — sobre essa
mesma base, com `save_as`, reabertura e build verdes. Nenhum documento
localizado nesta sessão registra explicitamente a resolução dos dois
bloqueadores de `docs/36` entre aquela medição e a `run-032` de `docs/46`.
**Isto é reportado como achado, não suavizado**: ou os dois bloqueadores
foram resolvidos por um commit não lido nesta sessão (candidato:
`59e8637` — "compiler version MEDIDA (3.5.18.50)", citado em `docs/18` mas
não lido em detalhe aqui), ou `docs/36` e as execuções W6-W9 estão medindo
elegibilidade por critérios diferentes. `CURRENT_STATUS.md` §3 trata a
questão como pendência ainda aberta ("aguardando remedição"); este documento
segue essa posição por ser a fonte canônica, mas a divergência aparente com
`docs/46`-`docs/49` (que rodaram com sucesso sobre a mesma base) não está
reconciliada em nenhum documento localizado.

> **RECONCILIADO na R0b.** O Template Profile
> [`config/template-profiles/mastertool-x-4.1.0.11-tmf-v1-io.json`](../config/template-profiles/mastertool-x-4.1.0.11-tmf-v1-io.json)
> registra, com proveniência por campo, o que faltava: `compiler_version`
> medida na `run-012` (commit `59e8637`) e inventário de 17 bibliotecas
> conferido por duas rotas na `run-016` (commit `a3b17f9`), ligados ao probe de
> qualificação em `a9dd252` — elegível desde a `run-018`. As duas hipóteses
> levantadas acima não eram excludentes e a primeira estava certa: os
> bloqueadores foram resolvidos por commits não lidos naquela sessão. `docs/36`
> **não foi editado** — ele descreve corretamente o que era verdade na
> `run-011`, e continua sendo evidência datada.

## 4. Compatibilidade read-only — resumo da sessão de 2026-07-31

`docs/27` §9: seis execuções, UI visível, offline, cópia descartável, **zero
diálogos, zero processos órfãos, SHA-256 da cópia idêntico nas seis**.
`probes/15` e `probes/21`, escritos para MasterTool 3.63, **rodaram sem uma
linha alterada** no MasterTool X. Riscos e proibições adicionais descobertos
nessa sessão (`SuppressPrompts`, `download_missing_libraries`,
`set_compilerversion_to_newest`, conceito de objeto transiente) estão em
[`CAPABILITY_MATRIX.md`](CAPABILITY_MATRIX.md) §4 e em
[`SAFETY_MODEL.md`](SAFETY_MODEL.md) §2.

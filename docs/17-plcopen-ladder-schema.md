# Schema real do PLCopen XML Ladder exportado pelo MasterTool

Registro do que o **arquivo real** contém — não do que o padrão PLCopen
sugeriria. Onde os dois divergem, este documento segue o arquivo.

Base: export de 2026-07-28 (run `2026-07-28_13-48-23`), um `functionBlock`
com 42 elementos, produzido por
`export_xml(stPath, False, False, False)` no MasterTool IEC XE 3.63.
O XML real **não é versionado** (contém nomes de equipamento, variáveis e
lógica do cliente). A fixture sanitizada equivalente está em
`tests/fixtures/plcopen/ladder_sample.xml`.

Gate: este documento fecha a descoberta do schema. **O modelo canônico só
deve ser desenhado a partir daqui.**

## As dez perguntas

### 1. Há redes explícitas?

**Não.** Não existe elemento `<network>`. Todos os elementos são irmãos
diretos de `<LD>`.

Redes são delimitadas por uma **extensão do fornecedor**: `<vendorElement>`
com `addData/data[@name=".../fbdelementtype"]` contendo `networktitle`.

Isso é confirmado por um segundo sinal independente: removendo os trilhos do
grafo e incluindo as arestas de `ParallelBranch`, os componentes conexos
não-triviais dão o **mesmo número** de redes que os marcadores. Duas fontes
independentes concordando é bem mais forte que confiar só na extensão
proprietária.

Cuidado: o último marcador do arquivo real **não tem rede depois dele**.
Comparar contagens sem descontar marcadores vazios produz divergência falsa.

### 2. Direção das referências

Do **destino para a origem**. O `<connectionPointIn>` do elemento que
consome contém `<connection refLocalId="N"/>` apontando para quem produz.

### 3. Todo elemento tem `localId` único?

Sim no arquivo observado. O mapa **verifica** em vez de assumir — `localId`
duplicado torna toda referência ambígua e vira diagnóstico.

`rightPowerRail` usa `localId="2147483646"`, um sentinela.

### 4. Como os pinos de blocos são identificados

Pelo atributo `formalParameter` em `<variable>`, dentro de
`<inputVariables>` / `<outputVariables>` / `<inOutVariables>`.

**`formalParameter` em `<connection>` NÃO é confiável como nome do pino de
origem.** No arquivo real, duas bobinas referenciam blocos `EQ` (cuja saída
declarada é `Out1`) usando `formalParameter` igual ao **nome da própria
variável da bobina**. Um parser que tratar esse atributo como pino de origem
quebra. O mapa denuncia a divergência e **preserva o valor bruto** em vez de
normalizar em silêncio.

### 5–6. Instância de FB, e como aparecem `TON` e outros

`addData/data[@name=".../fbdcalltype"]` → `<CallType>`:

| `CallType` | `instanceName` | exemplo observado |
|---|---|---|
| `operator` | ausente | `EQ`, `MOVE` |
| `functionblock` | presente | `TON` |

`typeName` sempre traz o tipo. `instanceName` só existe em bloco de função —
é o discriminador confiável.

### 7. Onde contatos e bobinas guardam suas variáveis

Depende do elemento, e a distinção é do próprio schema:

| elemento | onde | exemplo |
|---|---|---|
| `contact`, `coil` | filho `<variable>` | `<variable>NOME</variable>` |
| `inVariable` | filho `<expression>` | `<expression>NOME</expression>` |

Literais também aparecem como `<expression>` (`0`, `1`, `2`).

Atributos semânticos observados: `negated` (`true`/`false`) em contato e
bobina; `storage` (`none`/`reset`) em bobina; `edge` (`none`) em contato.
`set` não apareceu neste arquivo — ausência de observação, não de suporte.

### 8. Série e paralelo

**Série**: encadeamento direto por `refLocalId`.

**Paralelo**: extensão do fornecedor, **não** PLCopen padrão. Um
`<vendorElement>` com `data[@name=".../ldparallelbranch"]` contendo:

```xml
<ParallelBranch mode="sce">
  <BranchInput>  <!-- ponto comum de entrada -->
    <connectionPointIn><connection refLocalId="0"/></connectionPointIn>
  </BranchInput>
  <BranchTrees>  <!-- uma Tree por perna, apontando ao terminal dela -->
    <Tree><connectionPointIn><connection refLocalId="4" formalParameter="ENO"/></connectionPointIn></Tree>
    <Tree><connectionPointIn><connection refLocalId="10" formalParameter="ENO"/></connectionPointIn></Tree>
  </BranchTrees>
</ParallelBranch>
```

`mode="sce"` — significado não documentado; registrado como observado.

Consequência prática: **análise de conectividade que ignore essas arestas
conta redes a mais**, porque as pernas do paralelo aparecem desconexas.

### 9. Posição gráfica desempata?

**Não.** As 42 `<position>` do arquivo real são todas `x="0" y="0"`.
Qualquer estratégia que dependa de coordenadas falha neste export.

### 10. O que ainda não sabemos interpretar

- `mode="sce"` do `ParallelBranch`;
- `vendorElement` com `alternativeText` vazio e sem `ElementType`;
- `comment` com `content/xhtml` vazio — se comentários com texto aparecem
  em outro POU, o formato ainda não foi observado;
- `outVariable`, `inOutVariable`, `connector`, `continuation`, `jump`,
  `label`, `return` — **não apareceram**. Ausência de observação, não prova
  de ausência de suporte.

O mapa registra qualquer elemento fora da lista conhecida em
`unknown-elements.json`. Silêncio sobre elemento desconhecido é como um
parser começa a mentir.

## Inventário do arquivo real

| | |
|---|---|
| namespace | `http://www.plcopen.org/xml/tc6_0200` |
| elementos no `<LD>` | 42 |
| conexões (fora do `ParallelBranch`) | 29 |
| blocos | 10 (8 `operator`, 2 `functionblock`) |
| contatos / bobinas | 2 / 3 |
| `inVariable` | 14 |
| marcadores `networktitle` | 5 (1 sem conteúdo) |
| `ParallelBranch` | 1 |
| elementos desconhecidos | 0 |

## O que isto exige do modelo canônico

1. Rede não vem pronta — é reconstruída, e a reconstrução precisa dos **dois
   sinais** (marcador + topologia sem trilhos, com arestas de paralelo).
2. Aresta tem duas fontes distintas (`connectionPointIn` e `ParallelBranch`)
   e elas **não podem ser fundidas** sem perder que uma é não-padrão.
3. Pino de origem precisa ser resolvido pelos pinos **declarados pelo bloco**,
   nunca pelo `formalParameter` da conexão.
4. Nome de variável vem de campos diferentes conforme o elemento.
5. Coordenadas não existem — nenhuma heurística visual é possível.

# Contrato da topologia lógica Ladder

Define a camada intermediária entre a estrutura canônica e qualquer
interpretação de comportamento:

```text
evidência PLCopen → estrutura canônica → topologia lógica dirigida
                                        → semântica booleana
```

**Este documento termina na topologia lógica dirigida.** Nada aqui responde se
uma condição é verdadeira, se um contato está fechado ou o que uma rede faz.

## 1. Objetivo

Um modelo determinístico e rastreável da conectividade lógica de uma POU
Ladder. Ele responde:

- quais **terminais** estão conectados;
- qual a **direção lógica** observável, quando há base estrutural para afirmá-la;
- onde há **ramificação** e **convergência**;
- quais são **origens** e **destinos** dentro de cada rede;
- quais referências continuam **não resolvidas**;
- quais caminhos pertencem a **cada rede**.

E não responde nada além disso.

## 2. EntradasExemplo

A entrada é **exclusivamente** o `GraphicPOU` já produzido por
`plcopen/ladder_parser.py`:

| Do modelo canônico | Uso na topologia |
|---|---|
| `elements` | donos dos terminais |
| `pins` | terminais de bloco, com `formal_parameter` e `direction` |
| `connection_evidence` | as duas fontes de ligação, preservadas |
| `derived_edges` | adjacência já unificada, com pino de origem resolvido |
| `networks` | isolamento por rede |
| `diagnostics` | transportados, nunca descartados |
| `SourceRef` de cada objeto | rastreabilidade até `localId` |

**A camada de topologia não relê o XML.** Se um dado necessário não estiver no
modelo canônico, isso é lacuna do parser e se resolve lá — não abrindo o
arquivo por baixo. Reler introduziria uma segunda interpretação do mesmo
documento, e as duas divergiriam com o tempo.

## 3. Saída

```text
LogicalTopology
├── schema_version          inteiro, constante própria deste contrato
├── pou_identity            nome, tipo, namespace, arquivo de origem
├── networks[]              LogicalNetwork
├── diagnostics[]           os do canônico + os desta camada
└── source                  SourceRef da POU
```

```text
LogicalNetwork
├── network_id              determinístico (ver §8)
├── source_network_id       o `network_id` canônico que originou esta rede
├── nodes[]                 LogicalNode
├── edges[]                 LogicalEdge
├── roots[]                 node_ids sem aresta de entrada
├── sinks[]                 node_ids sem aresta de saída
├── branches[]              node_ids com fan-out > 1
├── joins[]                 node_ids com fan-in > 1
├── cycles[]                LogicalCycle
├── unresolved_connections[] conexões que NÃO viraram aresta
├── diagnostics[]
└── source
```

`schema_version` é **inteiro**, declarado em constante própria do módulo que
definir este artefato — família própria, sem constante global
(`docs/19-contratos-de-execucao.md`, seção 7).

## 4. Nós — terminais, não elementos

Um nó é um **terminal lógico**. Um elemento com entrada e saída produz dois
nós, não um.

```text
contact:12.input      contact:12.output
coil:31.input         coil:31.output
block:18.EN           block:18.ENO
block:18.In1          block:18.Out1
```

Representar o elemento inteiro como um nó apagaria a distinção entre "chega
em" e "sai de" — que é justamente a informação que a topologia existe para
carregar.

```text
LogicalNode
├── node_id                 determinístico (§8)
├── network_id
├── owner_element_id        `element_id` canônico
├── owner_local_id          `localId` do XML — rastreabilidade
├── owner_kind              `contact`, `coil`, `block`, `in_variable`, …
├── terminal_name           `EN`, `Out1`, `input`, `output`
├── terminal_direction      `input` | `output` | `inout` | `unknown`
├── terminal_role           `declared_pin` | `element_contract` | `inferred_absent`
├── resolution_status       `resolved` | `partially_resolved` | `ambiguous` | `unresolved`
├── source                  SourceRef
└── diagnostics[]
```

### 4.1 De onde vem `terminal_direction`

Duas origens legítimas, e nenhuma outra:

1. **`declared_pin`** — o bloco declara o pino em
   `inputVariables`/`outputVariables`/`inOutVariables`. A direção vem do grupo
   que o declarou. É a única fonte para terminais de `block`.
2. **`element_contract`** — o tipo de elemento define seus terminais no próprio
   schema PLCopen: `contact` e `coil` têm um `connectionPointIn` e um
   `connectionPointOut`; `inVariable` tem apenas saída; `leftPowerRail` apenas
   saída; `rightPowerRail` apenas entrada. Esses terminais não são declarados
   em lugar nenhum do arquivo — decorrem do tipo, e o contrato precisa
   nomeá-los explicitamente em vez de deduzi-los caso a caso.

**Nunca** de posição gráfica. As 42 `<position>` do export real são `(0,0)`
(`docs/17`); qualquer heurística visual é impossível aqui e continuaria errada
mesmo se as coordenadas existissem.

Quando o elemento não permite determinar o terminal — tipo desconhecido, pino
esperado ausente — o nó existe com `terminal_direction: unknown`,
`terminal_role: inferred_absent` e diagnóstico. **O nó não é omitido:** um
terminal que some leva a topologia a afirmar uma conectividade que o arquivo
não tem.

### 4.2 Terminais de elementos sem pinos declarados

| `owner_kind` | terminais | origem |
|---|---|---|
| `contact` | `input`, `output` | `element_contract` |
| `coil` | `input`, `output` | `element_contract` |
| `in_variable` | `output` | `element_contract` |
| `out_variable` | `input` | `element_contract` |
| `left_power_rail` | `output` | `element_contract` |
| `right_power_rail` | `input` | `element_contract` |
| `block` | um por `formal_parameter` declarado | `declared_pin` |
| `vendor_element` | conforme a extensão (§6.2) | `element_contract` |
| `comment` | nenhum | — |

Tipos modelados mas nunca observados (`inout_variable`, `connector`,
`continuation`, `jump`, `label`, `return`) **não recebem contrato aqui**. Quando
aparecerem, o contrato é estendido com base no arquivo real — não por
antecipação. Até lá, seus terminais são `unknown` com diagnóstico, e a
distinção `not_observed` ≠ `unsupported` do modelo canônico continua valendo.

## 5. Arestas

```text
LogicalEdge
├── edge_id                 determinístico (§8)
├── network_id
├── source_node_id          terminal de ORIGEM
├── target_node_id          terminal de DESTINO
├── direction_status        `resolved` | `partially_resolved` | `ambiguous` | `unresolved`
├── evidence[]              ids de ConnectionEvidence canônica
├── resolution_status
├── source
└── diagnostics[]
```

Uma aresta liga **terminal a terminal**, nunca elemento a elemento.

### 5.1 Evidência permanece distinta

`evidence[]` aponta para as `ConnectionEvidence` do modelo canônico, que
continuam separadas por `evidence_kind`:

```text
plcopen_connection
vendor_parallel_branch
```

Quando as duas sustentam a mesma aresta derivada, **ambas ficam listadas**. Não
fundir, não escolher uma, não normalizar para "conexão". Uma delas é extensão
proprietária, e o dia em que isso importar a informação precisa estar lá.

Evidência duplicada exata na mesma aresta gera `duplicate_edge_evidence` — é
sinal de que algo foi contado duas vezes, não motivo para descartar em
silêncio.

## 6. Direção

### 6.1 Quando uma direção é válida

`direction_status: resolved` exige as duas pontas identificadas
estruturalmente:

- **origem**: um terminal de saída identificado — pino declarado do bloco de
  origem (`resolved_from_declared_block_pins` no canônico), ou o terminal de
  saída que o contrato do tipo define;
- **destino**: um terminal de entrada identificado pela mesma via.

| `direction_status` | quando |
|---|---|
| `resolved` | origem e destino identificados estruturalmente |
| `partially_resolved` | uma ponta identificada, a outra conhecida só no nível do elemento |
| `ambiguous` | mais de um terminal candidato e nenhum critério estrutural para desempatar |
| `unresolved` | nenhuma ponta identificável |

**Só `resolved` e `partially_resolved` produzem `LogicalEdge`.** `ambiguous` e
`unresolved` vão para `unresolved_connections[]`, com a evidência original e o
motivo.

### 6.2 O que nunca determina direção

- posição gráfica, em qualquer circunstância;
- ordem de aparição no XML;
- proximidade de `localId`;
- o `formalParameter` da `<connection>` — ele **não é** declaração de pino. No
  arquivo real ele às vezes traz o nome da variável do DESTINO (`docs/17`,
  pergunta 4). Fica preservado como evidência bruta e nunca vira nome de
  terminal.

### 6.3 `unresolved_connections[]`

```text
UnresolvedConnection
├── connection_id
├── evidence_ids[]
├── reason              `ambiguous_direction` | `unresolved_source_reference` | …
├── candidate_nodes[]   terminais considerados, quando houver
├── source
└── diagnostics[]
```

Uma conexão não resolvida **nunca** vira aresta "provável". Uma topologia com
arestas prováveis é indistinguível de uma topologia errada.

## 7. Estrutura da rede

### 7.1 Roots e sinks — definição estrutural

```text
root = nó sem aresta lógica de ENTRADA dentro da rede
sink = nó sem aresta lógica de SAÍDA  dentro da rede
```

**Isso não é início nem fim de execução do CLP.** É propriedade do grafo. A
ordem de scan, o comportamento do trilho e a avaliação real pertencem à camada
semântica.

Uma rede pode ter zero roots (ciclo puro) ou zero sinks. Nenhum dos dois é erro
aqui — geram `network_without_root` / `network_without_sink` com severidade
informativa.

Trilhos, prólogo e elementos que o modelo canônico deixou em
`unassigned_elements` **permanecem fora das redes lógicas**. Não são anexados à
rede mais próxima nem à primeira: o canônico já decidiu que não pertencem a
nenhuma, e reverter essa decisão aqui seria inventar conectividade.

### 7.2 Branches e joins

```text
branch = nó com fan-out > 1
join   = nó com fan-in  > 1
```

Preservar fan-out, fan-in, paralelismo, convergência e a origem de cada
conexão. **Não deduzir equivalência booleana entre caminhos paralelos** —
saber que dois caminhos partem do mesmo terminal não diz nada, nesta camada,
sobre a relação lógica entre eles.

O `ParallelBranch` do fornecedor converge no `vendorElement` que o declara: o
`BranchInput` é a entrada comum e cada `Tree` é o terminal de uma perna. Os
terminais desse `vendor_element` seguem o contrato da extensão, e as arestas
correspondentes carregam `evidence_kind: vendor_parallel_branch`.

### 7.3 Isolamento de redes

Cada `LogicalNetwork` deriva de exatamente uma rede canônica
(`source_network_id`). Redes **não** são fundidas por nome, proximidade,
posição ou semelhança de conteúdo.

Uma aresta cujas pontas caem em redes canônicas diferentes gera
`cross_network_connection` e **não** é criada: ou o parser errou a
segmentação, ou o arquivo tem algo que ainda não entendemos. Nos dois casos, o
certo é registrar, não costurar.

**Conexão com elemento não atribuído é outra coisa** — e a distinção veio da
primeira derivação sobre a POU real, que produziu seis "erros" que não eram
erro nenhum. O trilho esquerdo alimenta todas as redes e está, por decisão do
canônico, em `unassigned_elements`. Toda conexão trilho → rede tem uma ponta
fora de qualquer rede lógica:

| Situação | Código | Severidade |
|---|---|---|
| rede A → rede B | `cross_network_connection` | **error** — segmentação inconsistente |
| sem rede → rede A | `unassigned_element_connection` | info — esperado, é o trilho |

Nos dois casos a aresta não é criada (não há nó do outro lado), mas só o
primeiro indica defeito. Tratar os dois como erro faria o trilho — presente em
toda rede real — parecer defeito estrutural, e o `error` perderia sentido.

## 8. Identidade determinística

IDs derivam de dados estáveis do arquivo:

```text
node_id     = "<network_id>:<owner_local_id>.<terminal_name>"
edge_id     = "<network_id>:<source_node_id>-><target_node_id>"
network_id  = derivado do `network_id` canônico
cycle_id    = "<network_id>:cycle:<menor node_id do ciclo>"
```

**Proibido** como fonte de identidade: índice de iteração instável, endereço de
memória, UUID aleatório, posição `(x, y)`, ordem incidental do parser XML,
timestamp.

Serialização determinística: chaves ordenadas, coleções ordenadas por id, e
dois parses do mesmo arquivo produzindo **bytes idênticos**.

## 9. Ciclos

```text
LogicalCycle
├── cycle_id
├── node_ids[]
├── edge_ids[]
├── detection_method     ex.: `dfs_back_edge`
└── source
```

Ciclos são **detectados e registrados**, nunca motivo de rejeição automática da
rede.

```text
ciclo observado ≠ programa inválido
```

Realimentação é construção legítima em Ladder. Se um ciclo torna um programa
inválido, isso é juízo semântico — e a camada semântica ainda não existe.
Rejeitar aqui seria decidir com informação que esta camada não tem.

### 9.1 Por que nenhum ciclo aparece hoje

Achado da implementação: **com nós-terminais e sem aresta interna, um laço
entre elementos não produz ciclo no grafo de terminais.**

Um `coil(1) → coil(2) → coil(1)` gera quatro nós (`1.input`, `1.output`,
`2.input`, `2.output`) e duas arestas — `1.output → 2.input` e
`2.output → 1.input`. Não há caminho fechado, porque nada liga `1.input` a
`1.output`.

Essa aresta interna **não deve existir nesta camada**. Afirmar que o sinal
atravessa um contato é afirmar que ele *conduz*, o que depende do valor da
variável e do tipo do contato (NA/NF) — semântica booleana, explicitamente
fora deste slice (§12). Modelá-la aqui seria pré-julgar a condução.

Consequências, todas esperadas:

- todo terminal de saída é `root` (nada entra nele) e todo terminal de entrada
  sem consumidor é `sink`. Por isso a POU real tem 14 roots numa rede de 22
  nós — é a forma correta do grafo nesta camada, não um defeito;
- `cycles[]` fica vazio no arquivo real. O detector existe, é testado sobre um
  grafo dirigido construído diretamente, e passará a produzir resultado quando
  a camada semântica introduzir travessia condicional.

Quando essa camada existir, a travessia será dela — e o contrato dela dirá sob
que condição o sinal passa.

## 10. Diagnósticos

| Código | Severidade | Significado |
|---|---|---|
| `missing_terminal` | warning | elemento não expôs um terminal esperado pelo seu contrato |
| `unknown_terminal_direction` | warning | direção não determinável estruturalmente |
| `unresolved_source_reference` | warning | origem não identificada |
| `unresolved_target_reference` | warning | destino não identificado |
| `ambiguous_direction` | warning | mais de um candidato, sem critério de desempate |
| `orphan_terminal` | info | terminal sem nenhuma aresta |
| `duplicate_edge_evidence` | warning | mesma evidência contada duas vezes |
| `unassigned_element_connection` | info | uma das pontas está fora de qualquer rede lógica |
| `cross_network_connection` | **error** | conexão atravessando **duas** redes canônicas |
| `cycle_detected` | info | ciclo presente — não é defeito |
| `network_without_root` | info | nenhum nó sem entrada |
| `network_without_sink` | info | nenhum nó sem saída |

`cycle_detected`, `network_without_root` e `network_without_sink` são
**informativos**: descrevem a forma do grafo, não um problema.
`cross_network_connection` é o único `error` — indica que a segmentação de
redes ou a resolução de referências está inconsistente, e seguir adiante
produziria topologia falsa.

Os diagnósticos do modelo canônico são **transportados**, não substituídos.

## 11. Regras obrigatórias

1. Não inferir direção por coordenadas.
2. Não usar posições `(0,0)` para ordenação nem desempate.
3. Usar os pinos declarados dos blocos.
4. Preservar separadamente `plcopen_connection` e `vendor_parallel_branch`.
5. Não gerar aresta válida a partir de conexão não resolvida.
6. Não fundir redes por proximidade, nome ou posição.
7. Detectar ciclos sem rejeição automática.
8. Preservar fan-out e fan-in.
9. Manter rastreabilidade até `localId`, terminal e origem XML.
10. Produzir saída determinística.
11. Não reinterpretar `formalParameter` da conexão como declaração de pino.
12. Não inserir semântica de execução nesta camada.

## 12. Fora do escopo

Explicitamente **não** interpretados aqui:

```text
contato normalmente aberto ou fechado      bobina comum, set ou reset
negação                                     TON, TOF, TP
borda positiva ou negativa                  comparadores
avaliação de expressões                     estado atual de variáveis
ordem completa de scan                      chamadas e estado interno de FBs
execução simbólica                          geração ou escrita de Ladder
FBD e SFC
```

A topologia carrega os dados que a semântica vai precisar — `negated`, `edge`,
`storage`, `type_name`, `instance_name` continuam nos elementos canônicos e
acessíveis pelo `owner_element_id`. Ela apenas não os **interpreta**.

## 13. Casos de teste previstos

Para a implementação (`feat: derive PLCopen Ladder logical topology`):

| # | Caso | O que prova |
|---|---|---|
| 1 | sequência linear | terminais encadeados, direção resolvida |
| 2 | fan-out | branch preservado, sem fusão de caminhos |
| 3 | fan-in | join preservado |
| 4 | ramificação via `vendor_parallel_branch` | extensão do fornecedor vira topologia |
| 5 | mesma aresta com duas evidências | ambas listadas, nenhuma descartada |
| 6 | pino de bloco resolvido | terminal vem do pino declarado |
| 7 | pino ausente | `missing_terminal`, nó existe com `unknown` |
| 8 | direção ambígua | vai para `unresolved_connections`, não vira aresta |
| 9 | conexão não resolvida | idem, com motivo registrado |
| 10 | rede com ciclo | detectado, registrado, rede **não** rejeitada |
| 11 | rede sem root | informativo, não erro |
| 12 | rede sem sink | informativo, não erro |
| 13 | múltiplas redes isoladas | sem contaminação entre redes |
| 14 | conexão entre redes | `cross_network_connection`, aresta não criada |
| 15 | todas as posições `(0,0)` | topologia correta sem usar coordenada |
| 16 | serialização determinística | dois parses, bytes idênticos |
| 17 | rastreabilidade completa | todo nó e aresta alcançam `localId` e origem |
| 18 | POU real atual | ver §14 |

Fixtures sintéticas para 1–17. O caso 18 usa o export real, que **nunca entra
no repositório**, e pula com motivo explícito quando ausente.

## 14. Números da POU real atual

A implementação deve reproduzir, sobre o export real já validado
(relatorios de validacao internos (nao publicados)):

| Do modelo canônico | |
|---|---|
| elementos | 42, nenhum `unknown` |
| pinos declarados | 40 |
| evidência de conexão | 32 = 29 `plcopen_connection` + 3 `vendor_parallel_branch` |
| arestas derivadas | 32 |
| redes | 4, todas `confirmed_by_marker_and_connectivity` |
| elementos não atribuídos | 8 |

Da topologia, medido na implementação (`feat: derive PLCopen Ladder logical
topology`) sobre o export de `2026-07-29_10-14-54`:

| | |
|---|---|
| `LogicalNetwork` | **4**, uma por rede canônica |
| nós (terminais) | 66 — 22, 8, 18, 18 |
| arestas | 26 |
| conexões não resolvidas | 6, **todas** `unassigned_element_connection` |
| diagnósticos de severidade `error` | **0** |
| evidências referenciadas | 32 de 32 — nenhuma perdida |
| `cross_network_connection` | nenhuma |
| ciclos | nenhum |

Há mais nós que elementos (66 > 42) porque um elemento com entrada e saída
produz dois nós — é a consequência direta de nós serem terminais.

Divergência entre estes números e uma execução futura é **achado**, não ajuste
de expectativa: significa que a topologia passou a ler o canônico de forma
diferente do que o parser produziu.

## 15. Critério de fechamento

Este contrato está pronto porque responde, sem ambiguidade:

| Pergunta | Seção |
|---|---|
| o que é um nó | §4 |
| o que é uma aresta | §5 |
| quando uma direção é válida | §6.1 |
| como redes são isoladas | §7.3 |
| como ramificações e junções são representadas | §7.2 |
| como ciclos são tratados | §9 |
| como evidências permanecem rastreáveis | §5.1, §8 |
| o que ainda **não** é semântica | §12 |

## 16. Depois deste contrato

```text
feat: derive PLCopen Ladder logical topology
```

Opera **somente** sobre o modelo canônico, reproduz a POU real e não introduz
semântica booleana. Só depois disso:

```text
feat: derive symbolic contact and coil semantics
```

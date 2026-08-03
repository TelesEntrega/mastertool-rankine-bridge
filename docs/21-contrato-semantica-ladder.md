# Contrato da semântica simbólica Ladder

Define a camada que transforma topologia em **símbolos, acessos e chamadas**:

```text
evidência PLCopen → estrutura canônica → topologia lógica dirigida
                  → semântica simbólica → [FORA DAQUI] avaliação de runtime
```

**Este documento termina na semântica simbólica.** Nada aqui responde se uma
rede energiza, se uma condição é verdadeira, em que ordem o scan avalia, ou o
que uma variável vale. Ele responde **quem lê o quê, quem escreve o quê, e quem
chama o quê** — com evidência e estado de resolução em cada afirmação.

## 1. Objetivo

Um índice determinístico e rastreável dos acessos simbólicos de uma POU Ladder,
capaz de sustentar as quatro perguntas do Gate L5 (`docs/14`):

```text
find reads <símbolo>      find calls <POU>
find writes <símbolo>     find callers <símbolo>
```

inclusive quando a evidência vem **exclusivamente** de uma POU Ladder, sem
nenhuma linha de Structured Text.

## 2. Entradas

Duas, e ambas obrigatórias:

| Entrada | Para quê |
|---|---|
| `GraphicPOU` (`plcopen/canonical_model.py`) | os atributos que carregam significado: `value_text`, `value_source_kind`, `negated`, `edge`, `storage`, `type_name`, `call_type`, `instance_name`, `interface`, `pins` |
| `LogicalTopology` (`plcopen/logical_topology.py`) | escopo de rede, terminais e a direção de pino já resolvida estruturalmente |

A topologia deliberadamente **não interpreta** os atributos do elemento
(`docs/20`, §12) — ela só garante que eles continuam alcançáveis por
`owner_element_id`. Esta camada é onde eles passam a significar algo. Por isso
precisa das duas entradas: uma sozinha não basta.

**Nada relê o XML.** Nem esta camada, nem nenhuma abaixo dela. Uma segunda
interpretação do mesmo documento divergiria da primeira com o tempo. Se um dado
necessário não está no canônico, a lacuna se resolve no parser.

**Nada re-deriva topologia.** Direção de conexão vem de `LogicalTopology` ou não
vem de lugar nenhum.

## 3. A iteração é sobre elementos canônicos

**Normativo:** a derivação percorre `GraphicPOU.elements` e usa a topologia para
localizar cada elemento numa rede. Não o contrário.

Percorrer os nós da topologia perderia todo elemento que o canônico deixou em
`unassigned_elements` — e um elemento fora das redes ainda pode carregar
símbolo. Quando isso acontece, o acesso é emitido com `network_id: null` e
diagnóstico `access_outside_networks`, nunca descartado.

Honestidade sobre o alcance desta regra: no export real atual, **nenhum** dos 8
elementos não atribuídos carrega `value_text` (§18). A regra não corrige nada
hoje; ela existe para que um arquivo futuro em que um contato caia fora das
redes não perca o acesso em silêncio.

## 4. Saída

```text
LadderSemantics
├── schema_version        LADDER_SEMANTICS_SCHEMA_VERSION — inteiro, constante própria
├── model_kind            "ladder_semantics"
├── pou_identity          nome, tipo, namespace, arquivo de origem
├── accesses[]            SymbolAccess
├── calls[]               LadderCall
├── diagnostics[]         os desta camada; os do canônico e da topologia não são copiados
└── source                SourceRef da POU
```

`schema_version` é **inteiro**, em constante própria do módulo — família
própria, sem constante global (`docs/19`, §7). A semântica evolui num ritmo que
não é o do canônico nem o da topologia.

Diagnósticos das camadas de baixo **não são copiados** para cá: eles já existem
nos seus artefatos, e duplicá-los criaria duas listas que divergem. Esta camada
emite só o que ela mesma descobre.

```text
SymbolAccess
├── access_id                 determinístico (§11)
├── network_id                id da rede lógica, ou null (§3)
├── owner_element_id          `element_id` canônico
├── owner_local_id            `localId` do XML — rastreabilidade
├── owner_kind                `contact`, `coil`, `in_variable`, …
├── owner_observation_status  `observed` | `not_observed` — do canônico, transportado
├── symbol_text               texto literal, nunca normalizado
├── symbol_source_field       `variable` | `expression` — de onde o texto veio
├── designation               `symbol` | `hardware_address` | `literal` | `expression`
├── classification            `read` | `write` | `read_write` | `not_applicable`
├── storage_operation         null | `set` | `reset` — só para `coil`
├── negated                   bool | null — preservado, não interpretado
├── edge_raw                  texto cru | null — preservado, não interpretado
├── storage_raw               texto cru | null — preservado
├── resolution_state          `resolved` | `partially_resolved` | `ambiguous` | `unresolved`
├── resolved_scope            `pou_interface` | `hardware_address` | `literal` | null
├── resolved_prefix           só em `partially_resolved`
├── unresolved_suffix         só em `partially_resolved`
├── reason                    motivo textual, quando não `resolved`
├── rule_applied              a regra que decidiu (§5, §6)
├── terminal_node_ids[]       nós da topologia que sustentam a direção
├── source                    SourceRef
└── diagnostics[]
```

```text
LadderCall
├── call_id                   determinístico (§11)
├── network_id                ou null
├── owner_element_id / owner_local_id
├── callee_text               `type_name` cru do bloco
├── call_type                 `operator` | `functionblock` | null — do canônico
├── instance_name             só quando `call_type == "functionblock"`
├── caller_pou                nome da POU contenedora
├── argument_bindings[]       ArgumentBinding
├── resolution_state
├── rule_applied
├── source
└── diagnostics[]
```

```text
ArgumentBinding
├── pin_formal_parameter      nome do pino DECLARADO — nunca o `formalParameter` da conexão
├── pin_direction             `input` | `output` | `inout` | `unknown`
├── bound_access_id           o acesso que este pino refina, ou null
├── evidence_ids[]            evidência canônica da conexão
└── resolution_state
```

## 5. Classificação por tipo de elemento

Tabela **normativa**. `rule_applied` registra qual linha decidiu:

| `owner_kind` | condição | `classification` | `rule_applied` |
|---|---|---|---|
| `contact` | — | `read` | `contact_reads_symbol` |
| `coil` | `storage` ausente ou `none` | `write` | `coil_writes_symbol` |
| `coil` | `storage` = `set` | `write` + `storage_operation: set` | `coil_set_writes_symbol` |
| `coil` | `storage` = `reset` | `write` + `storage_operation: reset` | `coil_reset_writes_symbol` |
| `in_variable` | — | `read` | `in_variable_reads_symbol` |
| `out_variable` | — | `write` | `out_variable_writes_symbol` |
| `block` | — | nenhum acesso; uma **chamada** (§8) | `block_invokes_callee` |
| `left_power_rail`, `right_power_rail` | — | nenhum acesso | — |
| `comment` | — | nenhum acesso | — |
| `vendor_element` | qualquer extensão conhecida | nenhum acesso | — |
| `unknown` | — | nenhum acesso + diagnóstico | `no_semantics_for_unknown_kind` |
| tipos de `NOT_OBSERVED_KINDS` | — | nenhum acesso + diagnóstico | `no_semantics_for_not_observed_kind` |

Uma bobina escreve **independentemente do sabor de `storage`**. Se o valor não
for reconhecido, a classificação permanece `write`, `storage_operation` fica
`null` e sai `unrecognized_storage_value` — falha-aberto na classificação,
falha-ruidoso no detalhe. Perder o `write` porque um atributo secundário veio
estranho seria o erro pior.

`storage` **também aparece em contatos** no export real, com valor `none`
(§18). Não é anomalia: é atributo default do fornecedor. `storage_operation` é
derivado **somente** para `coil`; em qualquer outro tipo o texto fica em
`storage_raw` e **não gera diagnóstico**. Sem esta regra a implementação
produziria avisos espúrios em cada contato.

`out_variable` recebe regra mas **não tem evidência real** — não aparece no
único export observado. Sua regra é exercitada por fixture sintética, e o
`owner_observation_status` do acesso registra isso. `not_observed` nunca vira
`unsupported`.

## 6. Refinamento por pino declarado

Um pino de bloco **não carrega símbolo**. Em Ladder o texto está no elemento
(`inVariable`, contato, bobina) que se conecta ao pino. O pino contribui uma
coisa só: **refinar a direção do acesso do elemento conectado**.

Precedência, nesta ordem exata:

1. **Pino declarado `inout`** — o acesso vira `read_write`, `rule_applied:
   pin_in_out_resolved`. Espelha deliberadamente o `var_in_out_resolved` do lado
   ST (`indexer/reference_resolver.py`), onde `VAR_IN_OUT` também sobrescreve a
   regra do operador.
2. **Contrato do tipo do elemento** (§5) em todos os outros casos.

O refinamento só se aplica quando **todas** estas condições valem:

- existe aresta de topologia com `direction_status` `resolved` ou
  `partially_resolved` entre o terminal do elemento e um nó de pino do bloco;
- o nó do pino tem `terminal_role: declared_pin`;
- o pino tem `direction` conhecida.

Se a direção do pino for `unknown`: vale o contrato do tipo, e sai
`pin_direction_unknown`.

Se a direção do pino **contradisser** o contrato do tipo — por exemplo um
`in_variable`, que só pode originar valor, ligado a um pino declarado `output` —
**o contrato do tipo prevalece** e sai
`pin_direction_conflicts_element_contract`. O contrato do tipo é estrutural: um
`inVariable` não tem terminal de entrada para receber nada. Confiar no pino
contra a estrutura inverteria um acesso real com base num arquivo malformado.
Registrar o conflito é obrigatório; resolvê-lo em silêncio, proibido.

`EN` e `ENO` são pinos como quaisquer outros: participam de `argument_bindings`,
refinam direção, e **não produzem acesso próprio**. O que alimenta um `EN` já
emite o seu próprio acesso pelo seu próprio tipo.

`inout` de pino **não tem evidência real**: o export atual tem 24 pinos de
entrada, 16 de saída e **nenhum** `inout` (§18). A regra existe porque foi
decidida explicitamente, e é exercitada por fixture sintética até que um arquivo
real a exercite.

## 7. O que o texto designa

`symbol_text` é o texto **literal**, nunca normalizado: não muda caixa, não
remove espaço interno, não resolve alias. A origem do campo é preservada em
`symbol_source_field` (`variable` para contato e bobina, `expression` para
`inVariable` — `docs/17`, pergunta 4), porque a origem é um fato do arquivo.

A classificação do texto usa o **lexer ST que já existe**
(`indexer/st_lexer.py: tokenize`), nunca uma expressão regular nova. Ele já
trata literal tipado (`T#5s`), número com base (`16#FF`), string, endereço de
hardware (`%IX0.0`) e palavra reservada. Uma regex ad-hoc erraria exatamente
esses casos, e teríamos duas noções de "identificador" no mesmo repositório.

| Tokens (fora `EOF`) | `designation` | `classification` | `resolution_state` |
|---|---|---|---|
| um `IDENTIFIER` | `symbol` | pela §5/§6 | §7.1 |
| `IDENTIFIER` (`.` `IDENTIFIER`)+ | `symbol` | pela §5/§6 | §7.1 |
| um `HW_ADDRESS` | `hardware_address` | pela §5/§6 | `resolved`, escopo `hardware_address` |
| um `NUMBER`, `TYPED_LITERAL`, `STRING`, `WSTRING` | `literal` | `not_applicable` | `resolved`, escopo `literal` |
| `KEYWORD` `TRUE`/`FALSE` | `literal` | `not_applicable` | `resolved`, escopo `literal` |
| qualquer outra combinação | `expression` | `not_applicable` | `unresolved`, motivo `expression_not_parsed` |

Um literal é acesso a **nada**: aparece na lista plana (não se perde) e em
nenhum balde de leitura ou escrita. `resolution_state: resolved` porque a
designação foi determinada **sem ambiguidade** — é um literal, e sabemos disso.
`unresolved` ali sugeriria símbolo faltando, que é outra coisa.

Um endereço de hardware é acesso real a uma localização, não a um símbolo
declarado: classifica normalmente (um contato sobre `%IX0.0` lê) com
`resolved_scope: hardware_address`. O lado ST já guarda `hardware_address` em
`VariableDeclaration`, então a Fase L6 tem por onde juntar os dois.

Uma expressão composta **não é decomposta**. Ela pode conter símbolos legíveis,
e extraí-los exigiria avaliar expressão — fora do escopo (§14). Fica um único
registro com o texto cru, `unresolved`, e diagnóstico `expression_not_parsed`.
Emitir acesso para pedaços de uma expressão que não sabemos analisar seria
afirmar leitura que não verificamos.

### 7.1 Resolução — e onde ela para

Esta camada resolve **apenas** contra a interface declarada da própria POU
(`GraphicPOU.interface`):

| Situação | `resolution_state` | `resolved_scope` |
|---|---|---|
| identificador simples que consta na interface | `resolved` | `pou_interface` |
| identificador pontuado cujo primeiro segmento consta | `partially_resolved` | `pou_interface` |
| identificador que não consta na interface | `unresolved` | null |

`unresolved` aqui **não** significa símbolo inexistente. Significa que a
resolução possível nesta camada não o alcança — tipicamente uma global, um GVL
ou um membro de DUT, que só o índice de símbolos do projeto resolve. Por isso o
diagnóstico é `symbol_not_in_pou_interface` com severidade `info`, e o motivo
textual diz exatamente isso. **Confundir "não resolvi aqui" com "não existe"
seria o erro mais fácil e mais grave desta camada.**

Resolução contra o índice ST do projeto é **Fase L6**, não esta. Fazê-la aqui
significaria construir um segundo resolvedor de símbolo ao lado de
`indexer/symbol_resolver.py`, e os dois divergiriam.

Em `partially_resolved`, os campos `resolved_prefix` / `unresolved_suffix` /
`reason` são preenchidos com o mesmo significado que têm em
`ResolvedReference` — vocabulário reusado de propósito, para a Fase L6 não ter
que traduzir.

## 8. Chamadas e callers

Cada elemento `block` produz **exatamente uma** `LadderCall`.

| Campo | Origem | Regra |
|---|---|---|
| `callee_text` | `type_name` do canônico | nunca inferido de `instance_name` |
| `call_type` | `call_type` do canônico | `operator` ou `functionblock`, transportado |
| `instance_name` | `instance_name` do canônico | só existe quando `call_type == "functionblock"` |
| `caller_pou` | `pou_identity.name` | a POU contenedora **é** o caller |

`type_name` ausente → `resolution_state: unresolved`, diagnóstico
`unresolved_callee`, e `callee_text: null`. **Nunca** derivar o callee do
`instance_name`: instância e tipo são coisas diferentes, e adivinhar uma pela
outra produziria um grafo de chamadas plausível e errado.

Duas incoerências entre `call_type` e `instance_name` são diagnóstico, nunca
correção silenciosa:

| Situação | Diagnóstico |
|---|---|
| `instance_name` presente com `call_type != functionblock` | `instance_name_without_functionblock` |
| `call_type == functionblock` sem `instance_name` | `functionblock_without_instance_name` |

`find calls <POU>` são as chamadas de **saída** de uma POU; `find callers
<símbolo>` são as de **entrada**, obtidas invertendo `callee_text → caller_pou`.
A direção segue a que `indexer/query.py` já documenta para ST — inverter uma das
duas faria as respostas de Ladder e ST se contradizerem sobre a mesma pergunta.

## 9. Preservado, nunca interpretado

`negated`, `edge_raw` e `storage_raw` viajam no acesso e **não afetam
classificação**:

- um contato negado continua `read`. A negação altera o que a rede *faz*, não
  quem ela *lê*;
- `edge` (borda) continua `read`. Detectar borda é comportamento;
- `storage` afeta apenas `storage_operation` (§5).

No export real, `edge` chega com o texto `"none"` em contatos — `"none"` é valor
**reconhecido** e significa ausência de borda, não valor inválido. Tratá-lo como
desconhecido produziria diagnóstico em arquivo perfeitamente normal.

## 10. Origem, regra e confiança

Toda afirmação carrega três coisas: **de onde veio** (`source`,
`owner_local_id`, `terminal_node_ids`, `evidence_ids`), **por que foi decidida
assim** (`rule_applied`) e **quanto vale** (`resolution_state`).

**`confidence` não é campo deste artefato.** Ela é derivada do
`resolution_state` pelo mapeamento fixo que já existe em
`indexer/query.py: confidence_for_state`:

```text
resolved            -> high
partially_resolved  -> medium
ambiguous           -> low
unresolved          -> none
```

Guardar `confidence` no artefato criaria uma segunda fonte para o mesmo fato, e
um dia as duas discordariam. O vocabulário de estados é **idêntico** ao do lado
ST justamente para que essa função sirva aos dois sem uma linha nova.

Os quatro valores são **literalmente** `resolved`, `partially_resolved`,
`ambiguous` e `unresolved` — as chaves de `_CONFIDENCE_BY_STATE`. Abreviar
qualquer um deles (`partial` em vez de `partially_resolved`, por exemplo) não
levanta erro: `confidence_for_state` mapeia estado desconhecido
defensivamente para `none`, e o acesso passaria a valer "nenhuma confiança"
sem que nada reclamasse. O teste de fechamento verifica que todo
`resolution_state` emitido é uma dessas quatro chaves.

`not_applicable` **não** é estado de resolução: é valor de `classification`
(§5, §7). Um literal tem `classification: not_applicable` e
`resolution_state: resolved` — os dois eixos são independentes, e fundi-los
faria "não é acesso" virar "não sei o que é".

### 10.1 Divergência de nome, registrada de propósito

| Camada | Campo |
|---|---|
| canônico e topologia | `resolution_status` |
| referências ST e **esta camada** | `resolution_state` |

Esta camada usa `resolution_state` porque é ela que alimenta o caminho de
consulta que já lê `resolution_state` (`indexer/query.py`). Renomear qualquer um
dos lados quebraria artefatos cobertos por checksum ou os cinco JSON do índice
ST — sem corrigir defeito algum. Os dois nomes **nunca convivem no mesmo
objeto**, e a divergência fica registrada aqui em vez de ser descoberta por
quem for escrever a Fase L6.

**Normativo para a Fase L6:** a adaptação entre os dois nomes acontece numa
**fronteira explícita e única** — uma tradução, num lugar, com teste próprio.
Proibido espalhar condicional que aceite os dois nomes pelo código: seria a
mesma decisão tomada em N lugares, divergindo em silêncio no primeiro que
alguém esquecesse de atualizar.

## 11. Identidade determinística, deduplicação e ordenação

Identidade sem contador, derivada só de dados estáveis — o mesmo formato de
`_node_id` da topologia (`network_id|local_id|terminal`):

```text
access_id = "<network_id ou 'unassigned'>|<owner_local_id>|access"
call_id   = "<network_id ou 'unassigned'>|<owner_local_id>|call"
```

Um elemento produz no máximo um acesso e no máximo uma chamada, então o par
`(rede, localId)` já é único. `localId` é único por POU — invariante checada no
canônico, e ela é o que sustenta esta identidade.

**`access_id` repetido é violação de invariante e levanta exceção**, nunca fusão
silenciosa. Duas ocorrências com a mesma identidade significam que algo foi
contado duas vezes; fundi-las esconderia o defeito.

O mesmo símbolo em elementos diferentes produz ocorrências **distintas**. Nunca
deduplicar por texto: um contato e uma bobina sobre o mesmo nome são uma leitura
*e* uma escrita, e colapsá-las apagaria metade da informação.

Ordenação (obrigatória, byte-a-byte estável entre duas execuções do mesmo
arquivo):

| Lista | Chave |
|---|---|
| `accesses[]` | `(network_id, owner_local_id)` |
| `calls[]` | `(network_id, owner_local_id)` |
| `argument_bindings[]` | `pin_formal_parameter` |
| `terminal_node_ids[]`, `evidence_ids[]` | ordem alfabética, sem duplicata |

**Proibido fabricar `line`/`column`** para parecer com o lado ST. O texto Ladder
não tem linha e coluna confiáveis, e inventá-las tornaria a evidência falsa e
ordenável por um critério inexistente. A Fase L6 decide como apresentar uma
localização Ladder ao lado de uma ST; ela tem `network_id` e `owner_local_id`
para isso, que são reais.

## 12. Diagnósticos

Severidade separada do código, como na topologia:

| Código | Severidade | Quando |
|---|---|---|
| `missing_symbol_text` | `warning` | contato, bobina ou variável sem `value_text` |
| `expression_not_parsed` | `info` | texto que não é identificador, endereço nem literal |
| `symbol_not_in_pou_interface` | `info` | identificador fora da interface — pode ser global; L6 resolve |
| `pin_direction_unknown` | `warning` | refinamento impossível, vale o contrato do tipo |
| `pin_direction_conflicts_element_contract` | `warning` | pino contradiz a estrutura do elemento (§6) |
| `unresolved_callee` | `warning` | `block` sem `type_name` |
| `instance_name_without_functionblock` | `warning` | §8 |
| `functionblock_without_instance_name` | `warning` | §8 |
| `unrecognized_storage_value` | `warning` | `storage` de bobina fora de `none`/`set`/`reset` |
| `unrecognized_edge_value` | `info` | `edge` fora dos valores conhecidos; nada nesta camada depende dele |
| `no_semantics_for_unknown_kind` | `info` | `kind == unknown`; o canônico já preservou o elemento |
| `no_semantics_for_not_observed_kind` | `info` | tipo modelado e nunca observado |
| `access_outside_networks` | `info` | elemento em `unassigned_elements` (§3) |
| `access_without_terminal_node` | `info` | acesso sem nó de topologia que o sustente |

Nenhum código com severidade `error`: **não existe arquivo Ladder que esta
camada deva recusar**. Um export malformado ainda tem acessos legítimos, e
rejeitá-lo inteiro esconderia tudo o que ele tem de bom. A camada relata; quem
decide o que fazer é o consumidor.

## 13. Regras obrigatórias

1. Não relê o XML; não re-deriva topologia.
2. Não infere direção de pino, símbolo, chamada ou acesso quando a evidência
   canônica é insuficiente — registra `unresolved` com motivo.
3. Nunca usa o `formalParameter` da `<connection>` como nome de pino ou de
   símbolo: no arquivo real ele às vezes traz a variável do **destino**
   (`docs/17`, pergunta 3).
4. Nunca usa posição gráfica, ordem de aparição no XML ou proximidade de
   `localId` para decidir nada.
5. Nunca deriva o callee do `instance_name`.
6. Nunca decompõe expressão composta.
7. Nunca funde ocorrências pelo texto do símbolo.
8. Nunca fabrica `line`/`column`.
9. Nunca converte `not_observed` em `unsupported`.
10. Nunca copia diagnóstico das camadas de baixo.
11. Não levanta exceção por conteúdo do arquivo — só por invariante interna
    violada (`access_id` duplicado).
12. Serialização determinística: duas execuções do mesmo arquivo produzem bytes
    idênticos.

## 14. Fora do escopo

Explicitamente **não** interpretados aqui:

```text
energização de rede            estado interno de FB
avaliação booleana             propagação de valores
ordem de scan                  execução condicional
equivalência lógica            simulação
avaliação de expressões        geração ou escrita de Ladder
resolução contra o índice ST    FBD e SFC
```

Os dois últimos merecem nome próprio: resolução de símbolo contra o projeto é
**Fase L6**; FBD e SFC são **Fase L8**. Nenhum dos dois é limitação — são
fatias, e antecipá-los aqui produziria código sem arquivo real que o exercite.

## 15. Divergências deliberadas com `docs/14` §L5

O roadmap foi escrito antes de o canônico, a topologia e o índice ST existirem
na forma atual. Três pontos dele são conscientemente ajustados; o roadmap será
reconciliado no slice de implementação.

**1. `read_write` é por ocorrência, não por símbolo.** O roadmap sugere que
`Motor` aparecendo como contato e bobina na mesma rede seja `read_write`. Isso
colidiria com o vocabulário ST, onde `read_write` qualifica **uma** ocorrência
que é simultaneamente leitura e escrita (o caso `VAR_IN_OUT`). Aqui: o contato
gera uma ocorrência `read`, a bobina uma `write`, e o símbolo aparece nos dois
baldes do índice agregado. `read_write` fica reservado ao pino `inout` (§6). Um
resumo por símbolo (`read` / `write` / `read_write`) é derivável do agregado por
quem precisar — sem sobrecarregar o vocabulário de ocorrência, que é o que a
Fase L6 vai unificar.

**2. Os cinco JSON do roadmap não são criados agora.** `ladder-networks.json`
duplicaria o artefato de topologia, e `ladder-diagnostics.json` seria uma
segunda cópia de uma lista que já viaja dentro do modelo. Esta camada define
**modelo e `to_dict()`**, como fizeram o canônico e a topologia — nenhuma das
duas escreve arquivo. Emissão de artefato entra quando existir consumidor, e
com o nome que o consumidor precisar.

**3. O Gate L5 é cumprido no modelo, não na CLI.** As quatro perguntas são
respondidas por uma superfície programática sobre `LadderSemantics`. Ligá-las a
`indexer/query.py` exige resolver símbolo Ladder contra `ProjectSymbolIndex` —
que é exatamente a Fase L6. Fazer a CLI responder já neste slice exigiria
inventar resolução de símbolo aqui, contra a §7.1.

## 16. Casos de teste previstos

Para a implementação (`feat: add Ladder semantic indexing`):

| # | Caso | O que prova |
|---|---|---|
| 1 | contato simples | `read` do símbolo |
| 2 | contato negado | continua `read`; `negated` preservado |
| 3 | contato com `edge="none"` | valor reconhecido, sem diagnóstico |
| 4 | bobina comum | `write`, `storage_operation: null` |
| 5 | bobina `set` e bobina `reset` | `write` com a operação preservada |
| 6 | bobina com `storage` estranho | continua `write`; `unrecognized_storage_value` |
| 7 | contato com `storage="none"` | nenhum `storage_operation`, **nenhum** diagnóstico |
| 8 | `inVariable` com identificador | `read` |
| 9 | `inVariable` com literal | `not_applicable`, `resolved`, escopo `literal` |
| 10 | `inVariable` com `%IX0.0` | `read`, escopo `hardware_address` |
| 11 | `inVariable` com expressão composta | um registro, `unresolved`, sem decomposição |
| 12 | `outVariable` | `write`; `owner_observation_status: not_observed` |
| 13 | pino declarado `inout` | `read_write`, `rule_applied: pin_in_out_resolved` |
| 14 | pino `unknown` | vale o contrato do tipo + `pin_direction_unknown` |
| 15 | pino que contradiz o tipo | contrato do tipo vence + diagnóstico |
| 16 | bloco `operator` | chamada sem `instance_name` |
| 17 | bloco `functionblock` | chamada com `instance_name`; caller é a POU |
| 18 | bloco sem `type_name` | `unresolved_callee`; callee **não** vem da instância |
| 19 | `instance_name` sem `functionblock` | diagnóstico, sem correção |
| 20 | símbolo fora da interface | `unresolved` + `info`, nunca "não existe" |
| 21 | identificador pontuado | `partially_resolved` com prefixo e sufixo |
| 22 | mesmo símbolo em contato e bobina | duas ocorrências; nenhuma fusão |
| 23 | elemento fora das redes com símbolo | acesso com `network_id: null` |
| 24 | `comment`, trilhos, `networktitle` | nenhum acesso, nenhum diagnóstico |
| 25 | tipo `unknown` e tipo não observado | diagnóstico `info`, sem semântica inventada |
| 26 | `access_id` duplicado | levanta exceção |
| 27 | serialização determinística | duas derivações, bytes idênticos |
| 28 | as quatro perguntas do gate | `reads`, `writes`, `calls`, `callers` numa POU só-Ladder |
| 29 | POU real | ver §17 |

Fixtures sintéticas para 1–28. O caso 29 usa o export real, que **nunca entra no
repositório**, e pula com motivo explícito quando ausente.

## 17. POU real — censo vinculado ao artefato

Todo número abaixo foi medido em 2026-07-30 **sobre este artefato**, e só vale
quando o hash confere:

```text
run      2026-07-29_10-14-54
arquivo  output/plcopen-export/export-root/pou-export
tamanho  25.226 bytes
sha256   c692040c39cc7bf656edd551d2ffdd1b41fecaa198b56b3182bd5149e1aeca13
```

**Fatos do modelo canônico** (medidos, não previstos):

| Distribuição dos 42 elementos | | Pinos declarados | |
|---|---|---|---|
| `in_variable` | 14 | `input` | 24 |
| `block` | 10 | `output` | 16 |
| `vendor_element` | 6 | `inout` | **0** |
| `comment` | 5 | | |
| `coil` | 3 | Interface: 8 variáveis | |
| `contact` | 2 | `inputVars` | 3 |
| trilhos | 2 | `outputVars` | 2 |
| | | `localVars` | 3 |

| Atributo | Observado |
|---|---|
| `value_text` presente | 19 elementos |
| `value_source_kind` | `expression` 14 (todos `in_variable`), `variable` 5 (2 contatos + 3 bobinas) |
| forma do texto | 11 identificadores simples + 8 literais — **nenhuma expressão composta, nenhum nome pontuado** |
| identificadores × interface | **11 de 11** constam na interface declarada |
| `negated` não nulo | 5 (2 contatos + 3 bobinas) |
| `edge` não nulo | 2, ambos com o texto `"none"` |
| `storage` não nulo | 5 — quatro `"none"` e um `"reset"` |
| `call_type` | `operator` 8, `functionblock` 2 |
| `type_name` | presente nos 10 blocos; nenhum ausente |
| `instance_name` | 2 — exatamente os dois `functionblock` |
| não atribuídos | 8: 5 `vendor_element`, 2 trilhos, 1 `comment` — **nenhum com `value_text`** |

**O que estes fatos decidem, e o que eles não decidem.** Aplicar §5–§7 ao censo
prevê 11 acessos simbólicos (2 leituras de contato, 3 escritas de bobina, 6
leituras de `inVariable`), 8 ocorrências `not_applicable` de literal, e 10
chamadas — todas com `resolution_state: resolved`, porque os 11 identificadores
estão na interface. Isto é **derivação das regras deste contrato sobre o censo**,
não medição de implementação alguma: nenhuma linha de código existe ainda.

A implementação **mede** os seus próprios números e os registra ao lado destes.
Divergência é **achado a investigar** — pode ser o censo, pode ser a regra, pode
ser a implementação — e não expectativa a ser ajustada nem alvo a ser forçado
por ajuste de código.

Três regras deste contrato ficam **sem evidência real** neste arquivo, e o
contrato diz isso em vez de fingir cobertura: pino `inout` (§6, zero pinos
`inout`), bobina `set` (§5, só `reset` aparece) e `out_variable` (§5, tipo não
observado). As três são exercitadas por fixture sintética, e o
`owner_observation_status` do acesso permite a um consumidor saber quais regras
nunca viram dado real.

### 17.1 Dívida a pagar no slice de implementação

`tests/unit/test_logical_topology.py` fixa os números da topologia contra o
caminho absoluto da run **sem conferir checksum algum**: se o conteúdo daquele
caminho mudar, o teste passa a validar outro arquivo silenciosamente e continua
verde. Requisito do gate do próximo slice, para as duas camadas:

```text
1. localizar o artefato — sem confiar silenciosamente num caminho absoluto
2. calcular o SHA-256
3. conferir contra c692040c…  → se divergir, NÃO validar as contagens
   como se fosse o mesmo artefato: falhar ou pular com motivo explícito
4. só então comparar as contagens exatas
```

A identificação reusa a informação ou o helper de
`tools/verify_plcopen_export_smoke.py` (commit `41c54db`); **não** se cria um
terceiro mecanismo de identificar o artefato. Fixture sintética continua a
cobertura principal — o artefato real é integração/regressão vinculada a
conteúdo específico, nunca a base da cobertura.

## 18. Critério de fechamento

Este contrato está pronto porque responde, sem ambiguidade:

| Pergunta | Seção |
|---|---|
| o que é lido e o que é escrito | §5 |
| como um pino muda isso | §6 |
| o que o texto do símbolo designa | §7 |
| até onde a resolução vai, e onde para | §7.1 |
| o que é chamada e quem é caller | §8 |
| o que é preservado sem ser interpretado | §9 |
| de onde vem a confiança | §10 |
| como nada é duplicado nem reordenado | §11 |
| o que é diagnóstico e com que severidade | §12 |
| o que **não** é semântica de runtime | §14 |
| onde o roadmap foi ajustado, e por quê | §15 |
| quais regras ainda não viram dado real | §17 |

## 19. Depois deste contrato

```text
feat: add Ladder semantic indexing
```

Opera **somente** sobre `GraphicPOU` + `LogicalTopology`, reproduz o censo da
POU real e não introduz avaliação de runtime. Só depois disso:

```text
Fase L6 — unificação com o índice ST: um índice, duas linguagens
```

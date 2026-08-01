# W6 — DUT provado, `create_task` exercido e recusado

> Registro de execução. `run-032` e `run-033`. Fecha `create_dut`, que estava
> bloqueado desde `docs/35` por uma afirmação minha que se provou errada — e
> deixa `create_task` explicitamente **não provado**, com o motivo medido.

## 1. Veredito

### `create_dut` funciona; `create_task` cria a task e não serve à fábrica

| Operação | Resultado | Estado |
| --- | --- | --- |
| `create_dut` | STRUCT e ENUM criados, persistidos, compilados — **0 erros, 0 avisos** | **`field_proven: True`** |
| `create_task` | task criada e persistida, build com 0 erros e **1 aviso** | **`field_proven: False`** |

<caption>

**Como ler:** as duas linhas descrevem execuções que *funcionaram*. A diferença
não é sucesso — é se a operação serve à fábrica. Uma task vazia compila com
aviso, e a fábrica existe para gerar projeto limpo.

</caption>

## 2. Números medidos

### `run-033` — a prova de DUT

| Grandeza | Valor |
| --- | --- |
| Spec | 2 DUTs (`ST_EIXO` STRUCT, `EN_ESTADO` ENUM) + PROGRAM que declara os dois |
| Plano | 12 passos — `04492dcc…` |
| Executados / delegados | 9 / 3 |
| Build | `build_verified` — 0 erros, **0 avisos** |
| Verificação | **3 de 3** objetos, 45 nós |
| Veredito | `factory_output_verified` |

A prova é conclusiva porque `PRG_EIXO` **declara** `stEixo : ST_EIXO` e
`enEstado : EN_ESTADO`. O compilador só diz algo sobre um DUT se alguém o
declarar.

### `run-032` — o que `create_task` produziu

```text
No POU is defined for task 'TaskDiagnostico'.
```

Zero erros, **um aviso**. A task existe, persistiu e reabriu.

## 3. Por que `create_task` não foi marcada como provada

Enchê-la exigiria vincular um PROGRAM a uma task que **não** é a do perfil. Para
isso não há caminho medido: a chamada idiomática escreve dentro de `UserPrg`,
que roda pela cadeia da `MainTask` (`docs/41`).

O executor **recusa explicitamente** esse pedido — e essa recusa é o guarda mais
importante que este marco produziu:

> *"o passo N pede chamada de PRG_X sob a task TaskNova, e a única forma medida
> de vincular um PROGRAM escreve dentro de UserPrg — que roda pela cadeia de
> MainTask. Vincular a outra task não tem caminho provado, e fazê-lo por UserPrg
> executaria o programa no ciclo errado."*

Sem ela, a spec pediria uma coisa e o projeto faria outra — **compilando limpo**.

**A API funciona; a operação não serve à fábrica ainda.** Marcar `field_proven`
aqui prometeria uma capacidade que não existe.

## 4. O bloqueio de DUT era meu, e é a quarta vez

`docs/35` §1 afirmava que os valores de `DutType` não estavam catalogados. Eles
estavam — no stub que o produto instala. A `run-031` (`docs/45`) mediu que o
enum é injetado no escopo do script.

O `type_guid` de DUT também estava faltando, e foi medido aqui:
`2db5746d-d284-4425-9f7f-2663a34b0ebc` — **o mesmo para STRUCT e ENUM**. O tipo
não distingue subtipo, exatamente como `docs/35` §4 já registrava para as
famílias de POU.

## 5. Dois vereditos mais fortes que a evidência, corrigidos

### A verificação dizia "verificado" com 1 de 3 objetos verificados

A família `duts` não tinha `type_guid` no mapa, e eu tratei *"não consegui
verificar"* como não-falha. `family_not_verifiable` bloqueia agora, e tem
**precedência** sobre `text_mismatch`: *"não medi"* é mais grave que *"medi e
diverge"*, porque a segunda ao menos foi medida.

**Medir não é verificar**, e isso virou código: família sem catálogo tem o
`type_guid` observado medido por busca só-por-nome e registrado numa nota — mas
o `outcome` continua bloqueando. Foi por esse caminho que o tipo de DUT entrou
no catálogo.

### O host só procurava o aviso de convenção

O build devolveu *"No POU is defined for task"* e o veredito saiu verde. Todo
aviso conta agora, e há veredito próprio — `AVISOS PRESENTES` — distinto de
`REPROVADO`: um pede olhar o projeto, o outro pede olhar a cadeia.

## 6. Limites

**O que a evidência comprova:** que `create_dut(name, DutType.Structure)` e
`create_dut(name, DutType.Enumeration)` criam objetos que sobrevivem a
`save_as`, reabrem e compilam quando **declarados** por um PROGRAM; e que
`create_task(name)` cria uma task que sobrevive a `save_as` e reabre.

**O que NÃO está comprovado:**

- **Que o CLP executa.** Inalterado.
- **`Alias` e `Union`.** O executor emite apenas `Structure` e `Enumeration`;
  `Alias` exige `baseType`, que é omitido.
- **Que uma task criada pode receber um POU.** Não há caminho medido, e o
  executor recusa.
- **Os parâmetros da task.** `kind_of_task`, `interval`, `priority` foram
  **lidos** no stub e nunca alterados — alterá-los é escrita de propriedade, que
  o vocabulário de operações do gate não cobre.
- **Determinismo de DUT.** Não repetido sobre cópias novas.
- **`n=1`** por operação.

## 7. Estado

`W6_PROVE_DUT_AND_TASK` e `W6_VERIFY_BUILD` foram **encerradas**.
`CONTROLLED_WRITE_PHASE = None`, `READ_ONLY_PHASE = True`.

**Dezesseis fases** abertas e encerradas; uma delas (`W1_4_INTEGRATED_BUILD`)
reaberta uma vez, com a mesma allowlist, para medir determinismo.

Das doze operações do vocabulário, **onze estão provadas em campo**. A que falta
é `create_task`, e a lista de operações em prova do executor tem exatamente ela.

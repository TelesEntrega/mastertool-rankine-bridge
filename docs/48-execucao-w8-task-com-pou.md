# W8 — a task com um POU dentro

> Registro de execução. `run-036`. Fecha `create_task`, a última operação do
> vocabulário sem prova, e o limite que `docs/46` §6 nomeou: *"que uma task
> criada pode receber um POU"*.

## 1. Veredito

### O aviso da `run-032` sumiu, e a task existe na saída com o programa dentro

| Grandeza | `run-032` (W6) | `run-036` (W8) |
| --- | --- | --- |
| Task criada | `TaskDiagnostico` | **a mesma** |
| POU dentro dela | nenhum | `PRG_DIAG` |
| Build | 0 erros, **1 aviso** | 0 erros, **0 avisos** |
| Saída reaberta | task vazia | **task com `PRG_DIAG` na posição 0** |

<caption>

**Como ler:** as duas medições juntas, e não qualquer uma delas sozinha.
*"0 avisos"* é ambíguo — uma task que tivesse sumido no `save_as` também não
avisaria nada. É a leitura da saída reaberta que distingue "a task está lá e
cheia" de "a task não está lá".

</caption>

O aviso que desapareceu, na íntegra:

> *"No POU is defined for task 'TaskDiagnostico'."*

## 2. O bloqueio era meu, e estava no lugar errado

`docs/46` concluiu que encher a task não tinha caminho medido. A conclusão
estava certa sobre `UserPrg` e **errada sobre o resto**: o aviso do fabricante
que W2 mediu nomeia a `MainTask`.

> *"A tarefa **MainTask** deveria conter apenas a chamada do programa MainPrg.
> Chamadas adicionais de outros programas devem ser realizadas a partir das POUs
> correspondentes do Perfil de Projeto"*

Ele está falando da task **do perfil**, cuja convenção é ser chamada de dentro
das POUs do perfil. Uma task que a spec cria não é ela, o perfil não diz nada
sobre ela, e `UserPrg` — que roda pela cadeia da `MainTask` — seria justamente
o caminho errado para alcançá-la.

**`add` nunca foi proibido; o receptor é que era.** A proteção era do objeto,
e eu a li como sendo do verbo.

## 3. Duas formas de vincular, duas operações de plano

Elas mutam objetos diferentes, e por isso não são a mesma operação com um
parâmetro:

| Operação | API | Alvo | Provada em |
| --- | --- | --- | --- |
| `create_program_call` | `replace` | texto de `UserPrg` | `docs/41` (W3) |
| `bind_program_to_task` | `add` | lista de POUs da task | **aqui** |

<caption>

**Como ler:** o roteamento é por TASK, não por spec. Quem escreve a spec pede
`program_calls`; quem decide o caminho é o planner.

</caption>

### Três recusas, e cada uma fecha um jeito diferente de errar

- **A forma idiomática apontada para task que não é a do perfil** — rodaria o
  programa no ciclo errado, compilando limpo. Era a recusa de `docs/46`, e
  continua.
- **A lista de POUs de uma task que o plano não cria** — ninguém leu o que já
  está nela, e acrescentar no fim mudaria a ordem de execução de um projeto que
  não foi gerado aqui. Vira lacuna nomeada no planner e recusa no executor.
- **Um vínculo cuja task não está entre as criadas nesta sessão** — a primeira
  lê o *plano*; esta lê o que a execução de fato criou.

O vínculo mede a lista antes e depois e exige exatamente o programa no fim: a
task nasce vazia, e é isso que torna `[]` → `["PRG_DIAG"]` uma grandeza
verificável. Um `add` que não acrescentasse nada passaria despercebido.

## 4. Como a task nasce — medido, e não escolhido

| Task | Tipo | Intervalo | Prioridade | Watchdog |
| --- | --- | --- | --- | --- |
| `MainTask` (template) | Cyclic | 100 ms | 13 | ligado, 1000 ms |
| `TaskDiagnostico` (criada) | Cyclic | **t#20ms** | **1** | **desligado** |

<caption>

**Como ler:** nenhum desses valores veio da spec. São os defaults do produto, e
a linha de baixo é mais rápida e de prioridade mais alta que a task principal —
no CODESYS, número menor é prioridade maior.

</caption>

Isto **não** é um defeito da execução: é o que o produto faz. É um limite da
fábrica, e está na seção 5. A spec **recusa** `interval` e `priority` com
`fail-closed` — o campo desconhecido não passa em silêncio —, então não há
promessa não cumprida; há capacidade ausente.

## 5. Limites

**O que a evidência comprova:** que `create_task(nome)` seguido de
`task.pous.add(programa)` cria uma task que sobrevive a `save_as`, reabre com o
programa na posição 0 da lista dela, e compila com zero erros e zero avisos.

**O que NÃO está comprovado:**

- **Que o CLP executa.** Inalterado, e permanente enquanto download e online
  forem proibidos.
- **Que a task roda no tempo certo.** Ela nasce com `t#20ms` e prioridade `1`,
  e a fábrica **não sabe mudar isso**. Escrever `kind_of_task`, `interval`,
  `interval_unit`, `priority` ou `watchdog.*` é **atribuição de propriedade** —
  uma classe de mutação que o vocabulário do gate, que guarda *chamadas de
  método*, não cobre. Enquanto isso não existir, uma spec com mais de uma task
  descreve a estrutura certa e o **tempo errado**.
- **Task preexistente.** Recusada nas duas portas, por não ter estado inicial
  conhecido.
- **Mais de um POU por task**, e a ordem entre eles. Um POU, uma task.
- **`comment`.** O `add` do stub aceita um segundo argumento, e ele não é
  passado — menos superfície mutável.
- **Determinismo.** `n=1`. As duas gerações de `docs/47` não incluíram task
  criada.
- **`Alias` e `Union`**, FB com herança ou interface, métodos e propriedades de
  FB, e as 17 bibliotecas *placeholder*: tudo como estava.

## 6. Estado

`W8_PROVE_TASK_WITH_POU` e `W8_VERIFY_BUILD` foram **encerradas**.
`CONTROLLED_WRITE_PHASE = None`, `READ_ONLY_PHASE = True`.

**Dezoito fases** abertas e encerradas. Das doze operações do vocabulário,
**as doze estão provadas em campo**, e a lista de operações em prova do
executor está vazia.

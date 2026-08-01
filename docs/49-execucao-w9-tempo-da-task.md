# W9 — a primeira escrita de propriedade

> Registro de execução. `run-037`. Fecha o limite que `docs/48` §5 nomeou em
> letras maiúsculas: *"a fábrica **não sabe mudar isso**"*.

## 1. Veredito

### A spec passa a dizer quando a task roda, e o produto obedece

| Propriedade | Nasceu com | A spec pediu | Depois do `save_as` e da reabertura |
| --- | --- | --- | --- |
| `kind_of_task` | Cyclic | Cyclic | Cyclic |
| `interval` | **`t#20ms`** | `t#500ms` | **`t#500ms`** |
| `interval_unit` | ms | ms | ms |
| `priority` | **`1`** | `25` | **`25`** |
| **`MainTask`** | 100 ms, prioridade 13 | *não tocada* | **100 ms, prioridade 13** |

<caption>

**Como ler:** a última linha é a que prova que a escrita foi na task **certa**,
e não em "uma task". Sem ela, quatro valores corretos na `TaskDiagnostico`
seriam compatíveis com uma fábrica que mexe em tudo que vê pela frente.

</caption>

Build: 0 erros, 0 avisos. Verificação: 3 de 3 objetos, 47 nós.

## 2. O gate não recusava — ele não enxergava

Até aqui este gate só sabia falar de **chamada de método**. `task.interval = x`
não era bloqueado: nenhum `assert` era alcançado, nenhuma allowlist consultada,
e a escrita simplesmente aconteceria. Uma classe inteira de mutação passava por
baixo do vocabulário.

A porta nova é **separada**, e não um nome a mais no registro de métodos, por
duas razões que uma função só apagaria:

- **A verificação estática é outra.** Chamada guardada é um `Call` com a guarda
  na linha imediatamente anterior; atribuição guardada é um `Assign` cujo alvo é
  um `Attribute`. Um teste que percorre `Call` nunca veria a segunda — e foi
  exatamente por essa fresta que a classe passou despercebida até a `run-036`.
- **O nome pode colidir.** `add`, `replace`, `insert` e `remove` são métodos
  catalogados e nomes plausíveis de campo. O prefixo `set:` torna a colisão
  impossível, e a allowlist de uma fase passa a dizer sem ambiguidade qual das
  duas coisas ela autorizou.

## 3. A allowlist é por propriedade, e não por operação

Uma spec que configura só o intervalo exige `set:interval` e mais nada:

```
required_allowlist:  add, build, create_gvl, create_program, create_task,
                     replace, save_as,
                     set:interval, set:interval_unit, set:kind_of_task,
                     set:priority
```

Um nome único para a operação inteira autorizaria as quatro de uma vez — a
abertura ampla com outro nome. A allowlist sai do **passo**, e o passo sai do
que a spec declarou.

### A ordem de escrita está no código, não na spec

`kind_of_task` primeiro, porque o próprio stub condiciona `interval` a ele já
ser Cyclic (L119-129). Escrever na ordem em que o autor digitou entregaria
`interval` num momento em que o produto pode recusá-lo.

## 4. O modo de falha próprio desta classe

Um método que não funciona **levanta**. Um campo simplesmente continua com o
valor antigo — e o projeto sai com o tempo errado, **compilando limpo**.

Por isso o executor relê cada propriedade depois de escrever e reprova se o
valor não pegou. Há teste com uma task *surda*, que aceita a atribuição e não
muda: sem a releitura, ela passaria como sucesso.

E não há `setattr` neste executor. Com ele, `configure_task` escreveria
qualquer campo do objeto do produto — inclusive os que ninguém catalogou — e a
allowlist por propriedade viraria enfeite: o gate autorizaria `set:interval` e
a linha escreveria outra coisa.

## 5. O que a spec recusa, e por quê

| Recusa | Motivo |
| --- | --- |
| `kind_of_task` fora do enum | Os seis membros são literais do stub |
| `Event`, `Status`, `ExternalEvent` | Exigem gatilho que o registro não cobre |
| `interval: '100ms'` | Não é nenhuma das **duas** grafias observadas |
| `priority: True` | `bool` é `int` em Python, e viraria 1 sem ninguém pedir |
| `priority: 99` | Fora de 0..31 |

<caption>

**Como ler:** as duas grafias aceitas — `t#500ms` e `100` — foram as duas
OBSERVADAS no produto (`docs/48` §4). Nenhuma terceira foi inventada.

</caption>

A faixa `0..31` **não foi medida**: é a convenção do CODESYS, declarada como
tal no código, e existe para que um valor absurdo morra no planner em vez de
virar uma task cuja prioridade ninguém sabe qual é.

## 6. Limites

**O que a evidência comprova:** que as quatro propriedades de tempo de uma task
criada pela fábrica podem ser escritas por uma spec declarativa, que os valores
sobrevivem a `save_as` e à reabertura, que o projeto compila sem erro nem aviso,
e que a task do perfil não é afetada.

**O que NÃO está comprovado:**

- **Que o CLP executa nesse tempo.** Inalterado, e permanente enquanto download
  e online forem proibidos. O `.project` diz `t#500ms`; ninguém mediu ciclo.
- **`watchdog`.** Receptor próprio (`ScriptWatchdog`), fora do registro.
- **`event`, `external_event`, `core_binding`, `parent_synchron_task`.**
  Settable no stub, e nenhuma spec deste projeto sabe escrevê-las — por isso
  `Event`, `Status` e `ExternalEvent` são recusados.
- **Task preexistente.** Recusada nas duas portas, como o vínculo.
- **A faixa de `priority`.** Convenção, não medição.
- **Determinismo.** `n=1`.
- **`Alias` e `Union`**, herança e interfaces de FB, métodos e propriedades de
  FB, as 17 bibliotecas *placeholder* e escala: tudo como estava.

## 7. Estado

`W9_PROVE_TASK_TIMING` e `W9_VERIFY_BUILD` foram **encerradas**.
`CONTROLLED_WRITE_PHASE = None`, `READ_ONLY_PHASE = True`.

**Vinte fases** abertas e encerradas. **Treze de treze** operações do
vocabulário provadas em campo, e as **duas classes de mutação** — chamada e
atribuição — exercidas contra o produto.

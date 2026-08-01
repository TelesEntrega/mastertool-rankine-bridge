# W4 — a fábrica de projetos

> Registro de execução. `run-027`, sobre o `TemplateExemplo v1.project`. É o marco que
> separa *"as operações estão provadas"* de *"a fábrica produz"* — e o primeiro
> em que nenhum nome de objeto aparece em código.

## 1. Veredito

### Uma spec vira um projeto que compila, e os nomes vêm só da spec

```
spec.json → planner (host, offline) → plano → executor → projeto → build
```

`GVL_FABRICA`, `PRG_BOMBA` e `PRG_PRESSAO` não existem em arquivo nenhum do
repositório. Trocar a spec troca o projeto gerado, sem tocar em código.

Até aqui cada marco tinha um probe com os nomes **fixos no fonte** — `probes/38`
cria exatamente uma `GVL_AI_TESTE` e um `PRG_AI_TESTE`. Isso provou as
operações; não fazia fábrica.

## 2. Números medidos

| Grandeza | Valor |
| --- | --- |
| Spec | 1 GVL, 2 PROGRAMs, 2 chamadas — `0df76f1f…` |
| Plano | **14** passos, emitido offline — `16a3584b…` |
| Passos executados | **11** |
| Passos delegados | **3** (`reopen`, `build`, `verify`) |
| Objetos criados | `GVL_FABRICA`, `PRG_BOMBA`, `PRG_PRESSAO` |
| Template | `59662579…` — **intacto** ao fim |
| Saída | `FABRICA.project`, `13aa9d88…` |
| Build | `build_verified` — 0 erros, **0 avisos**, 5 informações |
| Saída alterada pelo build | **não** |
| Verbos exigidos | `create_gvl, create_program, replace, save_as` |
| Verbos autorizados | os mesmos quatro |

<caption>

**Como ler:** "14 passos, 11 executados" não é execução parcial. Os três
restantes são `reopen`, `build` e `verify` — etapas de verificação com fase e
abertura próprias. Elas aparecem no artefato como `delegated`, porque *"o plano
tinha 14 passos e eu executei 11"* precisa estar escrito em algum lugar.

</caption>

## 3. O plano decide o quê; o executor decide como — e nenhum decide se pode

Três portas independentes, e todas literais:

| Porta | O que ela recusa |
| --- | --- |
| Planner (host) | operação fora do vocabulário; spec inválida; operação sem prova de campo |
| Executor | operação sem ramo escrito; texto cujo hash o plano não autorizou |
| Gate | verbo fora da allowlist **literal** da fase |

<caption>

**Como ler:** as três recusam por motivos diferentes. A do planner é sobre a
intenção, a do executor é sobre a capacidade, a do gate é sobre a permissão.
Uma só faria as três parecerem a mesma coisa.

</caption>

### O texto vem da spec, lacrado pelo hash do plano

O plano carrega `planned_after_sha256`; a spec carrega o texto; o executor lê da
spec, confere e só então escreve. **Um plano que carregasse o texto final
autorizaria a si mesmo a escrever qualquer coisa.**

`probes/38` resolvia isso fixando os textos no fonte — mais restrito, e
suficiente para um marco. Para uma fábrica não serve: os textos são do cliente.

### Tudo que pode reprovar, reprova antes da primeira mutação

Vocabulário, operação não implementada, texto ausente, hash divergente,
allowlist, GUID de linguagem. **A API não tem transação**: descobrir no passo 7
que ele é desconhecido deixaria a cópia com seis mutações e nenhuma forma de
desfazê-las.

## 4. Dois fail-opens fechados no caminho

### API catalogada não é operação provada

Uma spec com um `FUNCTION_BLOCK` saía com `executable: true` e
`create_function_block` na allowlist. A API está catalogada — mas W1.5 só a
exerceu para **ler o texto de nascimento** e descartar a cópia **sem salvar**.
Nada nunca provou que um FB sobrevive a `save_as` e compila.

O contrato do executor ganhou uma terceira coluna, `field_proven`, com
`evidence` obrigatório: provado sem artefato citado seria declaração, não
medição. **E o fail-open estava expresso como teste** —
`test_plan_without_gaps_is_executable` rodava sobre uma spec cheia de operações
nunca exercidas.

### A autorização era pedida para o que o plano descreve

A primeira execução reprovou com *"faltam: `['build']`"*. A recusa estava certa
e **a pergunta estava errada**: o plano descreve a cadeia inteira, inclusive o
build, e o build tem fase própria. Comparar o `required_allowlist` do plano com
a allowlist da fase de autoria reprovaria toda execução de fábrica, para sempre,
por uma operação que o executor nunca chama.

A exigência passou a ser derivada dos passos que ele **executa**. A direção
importa: derivar o *requisito* é legítimo; derivar a *permissão* seria a fase
deixando de autorizar coisa alguma.

## 5. O que a fábrica gera é o padrão que o fabricante indica

`create_program_call` **não** acrescenta o PROGRAM à lista da task. Ele compila
para um `replace` na POU de perfil — a forma medida em `docs/41`, com zero
avisos, contra um aviso pelo caminho de W2. `add` não aparece no executor, e há
teste garantindo que nenhuma entrada do contrato aponta para ele.

Task que já existe **não é criada**: `MainTask` vem no template, e `existing:
true` na spec suprime o passo. O default é `false` de propósito — quem não diz
nada está pedindo para criar, e criar task nunca foi exercido.

## 6. Limites

**O que a evidência comprova:** que uma especificação declarativa vira um
projeto MasterTool com GVLs e PROGRAMs nomeados pela spec, com textos
verificados por hash, chamados pelo caminho idiomático, e que o resultado
compila sem erros e sem avisos de convenção.

**O que NÃO está comprovado:**

- **Que o CLP executa.** Continua valendo: download e online são permanentemente
  proibidos. A afirmação máxima é *"o projeto declara"*.
- ~~**FB, FUNCTION e DUT.**~~ **FB e FUNCTION PROVADOS** na `run-028`
  (`docs/43`): criados, persistidos e compilados, com um PROGRAM que os
  instancia e chama. **DUT continua bloqueado** — os valores do enum `DutType`
  não estão catalogados.
- ~~**`create_task`.** Nunca exercido.~~ **EXERCIDO e NÃO provado** na
  `run-032` (`docs/46`): a task é criada e persiste, mas compila com aviso, e
  não há caminho medido para pendurar um PROGRAM numa task que não seja a do
  perfil.
- ~~**Determinismo da fábrica.**~~ **MEDIDO** em `docs/44` (`run-029` e
  `run-030`): a mesma spec produziu dois arquivos de bytes distintos e um único
  projeto. Ainda `n=2`, e sem FB nem FUNCTION na spec repetida.
- **Uma única execução.** `run-027` é n=1. Tudo aqui vale para uma spec, um
  template, uma máquina.
- **Specs grandes.** A maior exercida em campo tem três objetos. O limite do
  executor é 512 passos, mas nada perto disso foi medido.
- **Bibliotecas.** As 17 do template continuam *placeholder*, e a spec aceita
  `libraries` sem que nada as resolva.
- **O texto da chamada idiomática não é lacrado por hash.** É o único. O planner
  é offline e não pode saber o que há dentro de `UserPrg`; o que ele fixa é o
  **nome** do programa chamado. Os hashes antes/depois vão para o log com
  `not_hash_sealed_by_plan: true`.

## 7. Estado

`W4_EXECUTE_PLAN` e `W4_VERIFY_BUILD` foram **encerradas**, cada uma em commit
próprio. `CONTROLLED_WRITE_PHASE = None`, `READ_ONLY_PHASE = True`.

**Doze fases** abertas e encerradas; uma delas (`W1_4_INTEGRATED_BUILD`)
reaberta uma vez, com a mesma allowlist, para medir determinismo.

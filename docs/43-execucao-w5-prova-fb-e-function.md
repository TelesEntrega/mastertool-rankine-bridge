# W5 — FUNCTION_BLOCK e FUNCTION provados em cadeia

> Registro de execução. `run-028`, pela fábrica. Fecha a lacuna que `docs/42`
> §6 nomeou primeiro: *"FB, FUNCTION e DUT — nenhum dos três passou por cadeia
> que persistiu e compilou"*.

## 1. Veredito

### Os dois sobrevivem a `save_as` e compilam — e a prova só vale porque o PROGRAM os usa

`FB_RAMPA` e `F_DOBRO` foram criados pela fábrica, tiveram texto escrito,
foram persistidos e compilaram com **zero erros**.

O que torna isso conclusivo não é a criação: é que `PRG_PROVA` declara
`fbRampa : FB_RAMPA` e chama `F_DOBRO(fbRampa.rSaida)`. **Criar os dois e
deixá-los soltos provaria que a API cria objeto, não que o objeto serve** — o
compilador só diz algo sobre eles se alguém os instanciar. Um nascimento
quebrado teria reprovado no `Typify code`.

## 2. Números medidos

| Grandeza | Valor |
| --- | --- |
| Spec | GVL + FB + FUNCTION + PROGRAM que usa os dois — `46dc8e85…` |
| Plano | **16** passos — `1f9d665c…` |
| Executados / delegados | **13** / 3 |
| Criados | `GVL_PROVA`, `F_DOBRO` (`REAL`), `FB_RAMPA`, `PRG_PROVA` |
| Template | `59662579…` — **intacto** |
| Saída | `1807dbe8…` |
| Build | `build_verified` — 0 erros, **0 avisos**, 5 informações |
| Saída alterada pelo build | **não** |

<caption>

**Como ler:** `F_DOBRO` aparece com `return_type: REAL` porque o tipo de retorno
é obrigatório na assinatura catalogada e vem **do plano** — o executor não
escolhe um. Uma FUNCTION sem `return_type` reprova antes da primeira mutação.

</caption>

## 3. O ovo-e-galinha, e por que a saída não foi um bypass

O planner é fail-closed em `field_proven`: não emite plano executável com
operação nunca exercida. Mas **sem executar não há como exercê-la**.

A saída errada seria marcar `field_proven: True` antes de medir — exatamente o
fail-open que `docs/42` §4 fechou. A saída certa foi a **allowlist**:

```text
W5_PROVE_IEC_PACKAGE   create_gvl, create_program, create_function_block,
                       create_function, replace, save_as
```

Escrever `create_function_block` ali, à mão, em `safety.py`, **é** a decisão
humana de que aquela execução existe para exercer aquela operação. Não há
interruptor que dispense isso.

### Quatro recusas que a exceção não abre

| Situação | Resultado |
| --- | --- |
| Lacuna de outro tipo (GUID não medido) | reprova — a fase não redime o que não nomeia |
| Fase sem o verbo na allowlist | reprova — ninguém decidiu provar nada |
| Operação fora de `PROVING_OPERATIONS` | reprova — `create_task` não vira provável por decreto |
| Fase da fábrica (`W4_EXECUTE_PLAN`) | reprova — produzir e provar são marcos diferentes |

<caption>

**Como ler:** cada linha tem teste próprio. A exceção é estreita de propósito —
uma exceção que cobrisse "qualquer lacuna" seria o gate desligado com outro
nome.

</caption>

### A lista de operações em prova **encolhe**

Depois da `run-028`, `PROVING_OPERATIONS` voltou a ficar **vazia**, e há teste
exigindo que esteja: toda operação que o executor implementa está provada, com
`evidence` citando doc e run. Uma lista que só crescesse seria o inventário do
que o executor faz sem prova, indefinidamente.

O **mecanismo** continua testado mesmo com a lista vazia — um teste simula uma
operação não provada e confere que a fase continua sendo quem desempata. Sem
isso, o próximo marco descobriria o caminho quebrado só ao precisar dele.

## 4. Efeito prático

Uma spec com `FUNCTION_BLOCK` e `FUNCTION` agora produz plano `executable: true`
e roda pela fábrica normal, **sem fase de prova nenhuma**. A fábrica passou a
gerar blocos reutilizáveis — que é o que código de máquina de verdade usa.

## 5. Limites

**O que a evidência comprova:** que `create_function_block(name, language)` e
`create_function(name, return_type, language)` criam objetos que sobrevivem a
`save_as`, reabrem, e compilam quando **instanciados e chamados** por um
PROGRAM.

**O que NÃO está comprovado:**

- **Que o CLP executa.** Inalterado: download e online permanecem proibidos.
- **`DUT`.** Continua bloqueado — os valores do enum `DutType` não estão
  catalogados (`docs/35` §1), e chamar sem o subtipo certo seria inventar a API.
  Nunca entrou em allowlist alguma, nem na fase cujo propósito era provar
  operação nova.
- **`create_task`.** Nunca exercido.
- **`base_type` e `interfaces` do FB.** Omitidos de propósito — são opcionais
  catalogados, e passar valor decidiria de antemão algo que ninguém mediu.
  Herança de FB e implementação de interface seguem **não medidas**.
- **FB com mais de um método, ações, ou propriedades.** O FB provado tem
  declaração e implementação e nada mais.
- **`n=1`.** Uma execução, uma spec, um template, uma máquina.
- **Determinismo.** Não repetido sobre cópias novas.

## 6. Estado

`W5_PROVE_IEC_PACKAGE` e `W5_VERIFY_BUILD` foram **encerradas**, cada uma em
commit próprio. `CONTROLLED_WRITE_PHASE = None`, `READ_ONLY_PHASE = True`.

**Catorze fases** abertas e encerradas; uma delas (`W1_4_INTEGRATED_BUILD`)
reaberta uma vez, com a mesma allowlist, para medir determinismo.

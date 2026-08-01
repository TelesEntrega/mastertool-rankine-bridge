# W7 — a fábrica com todas as operações provadas

> Registro de execução. `run-034` e `run-035`, a mesma spec de máquina sobre
> cópias novas. Fecha três limites que `docs/42` §6 nomeou: *"specs grandes"*,
> *"determinismo da fábrica"* e *"FB, FUNCTION e DUT"*.

## 1. Veredito

### Uma máquina inteira, de uma spec, duas vezes, com o mesmo conteúdo

Sete objetos de **cinco famílias**, com dependência real entre eles, gerados de
uma especificação declarativa e compilados sem erro nem aviso.

| Grandeza | `run-034` | `run-035` |
| --- | --- | --- |
| Plano | 24 passos — `38e35540…` | **o mesmo** |
| Executados / delegados | 21 / 3 | 21 / 3 |
| Objetos criados | 7 | 7 |
| Build | 0 erros, **0 avisos** | idem |
| Verificação | **7 de 7**, 49 nós | idem |
| **`.project`** | `257991e4…` | **`25c275d9…`** |

<caption>

**Como ler:** a única linha que difere é a que nunca foi critério. Nove
`object_guid` distintos provam que as gerações são independentes — sem essa
contraprova, "igual" seria tautologia sobre o mesmo arquivo.

</caption>

## 2. O projeto gerado

```text
EN_MODO      (ENUM)    Manual, Automatico, Falha
ST_EIXO      (STRUCT)  usa EN_MODO
GVL_MAQUINA  (GVL)     usa ST_EIXO
F_ESCALA     (FUNCTION : REAL)
FB_RAMPA     (FB)      chama F_ESCALA, usa EN_MODO
PRG_EIXO     (PROGRAM) instancia FB_RAMPA, declara ST_EIXO, lê GVL_MAQUINA
PRG_SUPERVISAO (PROGRAM) chama F_ESCALA, lê GVL_MAQUINA
```

Os dois PROGRAMs foram vinculados pelo caminho idiomático — chamados de dentro
de `UserPrg`, não acrescentados à lista da task (`docs/41`).

**Nenhum objeto ficou solto.** O compilador só diz algo sobre um objeto se
alguém o usar: um DUT precisa ser declarado, um FB instanciado, uma FUNCTION
chamada. Uma spec com sete objetos que não se referenciam provaria bem menos.

## 3. Onze das doze operações, numa só execução

`W7_FACTORY_FULL` **não alarga nada**: ela é a união das allowlists de autoria
de W1.4, W3, W5 e W6, menos `build`, `add` e `create_task`. Há teste afirmando
essa igualdade — se aparecer nela um verbo que nenhum marco provou, a igualdade
quebra.

| Verbo | Provado em |
| --- | --- |
| `create_gvl` | W1.1, W1.4 |
| `create_program` | W1.2, W1.4 |
| `create_function_block` | W5 (`run-028`) |
| `create_function` | W5 (`run-028`) |
| `create_dut` | W6 (`run-033`) |
| `replace` | W1.3A, W1.3B, W3 |
| `save_as` | todas |

<caption>

**Como ler:** a fase da fábrica é a soma do que já foi medido, e nada além.
`W4_EXECUTE_PLAN` continua no mapa como registro — ela era a fábrica quando a
fábrica sabia menos.

</caption>

## 4. Limites

**O que a evidência comprova:** que uma especificação declarativa com cinco
famílias e dependências cruzadas vira um projeto MasterTool cujos sete objetos
existem com o tipo certo, cujos textos relidos do disco batem com o hash que o
plano autorizou, que compila sem erros nem avisos, e cujo conteúdo é idêntico
entre duas gerações independentes.

**O que NÃO está comprovado:**

- **Que o CLP executa.** Inalterado, e permanente enquanto download e online
  forem proibidos.
- **`create_task` útil.** A única operação sem prova. A task é criada e compila
  com aviso; não há caminho medido para lhe dar um POU (`docs/46`).
- **Escrita de propriedade.** `kind_of_task`, `interval`, `priority` foram lidos
  no stub e nunca alterados — o vocabulário de operações do gate cobre **chamadas
  de método**, não atribuição de propriedade. Essa é uma classe de mutação que o
  modelo de segurança ainda não tem.
- **Bibliotecas.** As 17 do template continuam *placeholder*, e a spec aceita
  `libraries` sem que nada as resolva.
- **`Alias` e `Union`.** O executor emite apenas `Structure` e `Enumeration`.
- **Escala real.** Sete objetos e 24 passos. O limite do executor é 512 passos,
  e nada perto disso foi medido.
- **Outra máquina, outra instalação, outro template.** Tudo aqui é `4.1.0.11`
  sobre o `TemplateExemplo v1.project`, na mesma máquina.
- **`n=2`.** `docs/40` mediu cinco gerações da cadeia de W1.4; aqui são duas.

## 5. Estado

`W7_FACTORY_FULL` e `W7_VERIFY_BUILD` foram **encerradas**.
`CONTROLLED_WRITE_PHASE = None`, `READ_ONLY_PHASE = True`.

**Dezoito fases** abertas e encerradas; uma delas (`W1_4_INTEGRATED_BUILD`)
reaberta uma vez, com a mesma allowlist, para medir determinismo.

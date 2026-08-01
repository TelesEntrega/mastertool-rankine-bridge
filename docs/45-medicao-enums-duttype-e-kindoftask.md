# `DutType` e `KindOfTask` — medição de alcance

> Registro de execução. `run-031`, somente leitura, sem fase aberta. Corrige
> uma afirmação de `docs/35` §1 que bloqueou `create_dut` desde que foi escrita.

## 1. Veredito

### Os dois enums estavam catalogados o tempo todo, e são injetados no escopo do script

| Enum | Stub | Alcance medido | Confere com o stub |
| --- | --- | --- | --- |
| `DutType` | `ScriptIecLanguageObjectContainer.pyi` L23 | `script_globals["DutType"]` | **sim** |
| `KindOfTask` | `ScriptTaskConfigObject.pyi` L5 | `script_globals["KindOfTask"]` | **sim** |

<caption>

**Como ler:** "alcance" e "catálogo" são perguntas diferentes. O stub descreve a
superfície .NET; o que um script IronPython consegue **nomear** depende do que o
engine injeta. Os dois foram resolvidos **no primeiro caminho tentado** — nem
`import` foi preciso.

</caption>

```text
DutType      Structure, Enumeration, Alias, Union
KindOfTask   Cyclic, Freewheeling, Event, ExternalEvent, Status, ParentSynchron
```

## 2. O erro que isto corrige

`docs/35` §1 afirmava:

> *"**Nenhum dos valores do enum `DutType` está catalogado** em `docs/27` nem em
> `api/mastertool-api-observations.md`"*

A afirmação sobre **aqueles dois documentos** era verdadeira. A conclusão tirada
dela — que a API não estava catalogada e que `create_dut` estava bloqueado — não
era. O enum está no stub que o **próprio produto instala**.

**É a quarta vez.** As três anteriores estão em `docs/27` e `docs/36`, e a regra
que saiu delas é a mesma: *consultar os `.pyi` antes de dizer "não catalogado"*.
O que falhou aqui não foi a regra — foi eu não a aplicar a um documento escrito
antes de ela existir, e depois tratar aquele documento como medição.

### O que o instrumento mede, e o que ele recusa medir

`docs/35` nomeou o instrumento que faltava: *"reflexão estática sobre o enum
`DutType`"*. O `probes/48` é esse instrumento, com duas escolhas deliberadas:

- **Lê membro por nome literal**, vindo de uma tupla do módulo. Enumerar os
  membros do objeto descobriria nomes que ninguém catalogou — e este probe
  existe para **conferir** o catálogo, não para expandi-lo em silêncio.
- **"Não alcancei" nunca vira "não existe".** Falhar nos quatro caminhos produz
  `unreachable` com a lista do que foi tentado, e o texto diz explicitamente que
  isso *não* significa ausência.

## 3. O que isto desbloqueia

| Operação | Estado antes | Estado agora |
| --- | --- | --- |
| `create_task(name)` | `field_proven: False` | enum alcançável; falta **provar em cadeia** |
| `create_dut(name, type, baseType)` | bloqueada por "enum não catalogado" | enum alcançável; falta **provar em cadeia** |

<caption>

**Como ler:** alcançar o enum não prova nada sobre a operação. As duas continuam
`field_proven: False`, e o planner continua recusando plano executável com elas
— corretamente. O que mudou é que agora **existe caminho** para prová-las.

</caption>

## 4. Limites

**O que a evidência comprova:** que `DutType` e `KindOfTask` são nomeáveis no
escopo de um script do MasterTool X `4.1.0.11`, e que seus membros são
exatamente os que os stubs declaram.

**O que NÃO está comprovado:**

- **Que `create_dut` funciona.** Nenhuma chamada foi feita. O enum ser
  alcançável é condição necessária, não suficiente.
- **Que `create_task` funciona.** Idem.
- **Que o valor do enum é aceito pelo binding.** `create_program` aceitava
  `Guid` e recusava `str` (`run-005`); nada garante que um membro de enum
  atravesse o binding sem conversão. Isso é medição de outra execução.
- **Que os outros membros servem.** `Alias` e `Union` exigem `baseType`, e
  `Event`/`ExternalEvent` exigem campos que ninguém preencheu.

## 5. Estado

Nenhuma fase foi aberta. `READ_ONLY_PHASE = True`,
`CONTROLLED_WRITE_PHASE = None`. O probe não cria, não salva e não compila —
há teste estático garantindo que nenhuma dessas cadeias aparece no arquivo.

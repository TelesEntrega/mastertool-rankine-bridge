# Contrato do pacote IEC mínimo — FB, FUNCTION, DUT (STRUCT, ENUM)

Documento **normativo**, complementar a
[`28-contrato-escrita-controlada-mastertool-x.md`](28-contrato-escrita-controlada-mastertool-x.md).
Onde este contrato divergir do `docs/28`, o `docs/28` prevalece — este
documento só estende o vocabulário e a allowlist para quatro famílias de
objeto IEC que `docs/28` §13 deixou explicitamente **fora** da primeira
mutação: `FUNCTION_BLOCK`, `FUNCTION` e `DUT` (nas variantes `STRUCT` e
`ENUM`).

**Este documento não autoriza operação nenhuma.** `READ_ONLY_PHASE` continua
`True`, `CONTROLLED_WRITE_PHASE` continua `None`. Nenhuma linha de código,
nenhum probe e nenhuma execução foram produzidos por este slice — é
documento apenas.

A evidência que sustenta as afirmações abaixo está em
[`27-reconhecimento-mastertool-x.md`](27-reconhecimento-mastertool-x.md) §7 e
em [`api/mastertool-api-observations.md`](api/mastertool-api-observations.md).
Este contrato não repete medição nova; ele decide regra sobre medição já
feita e declara lacuna onde medição não existe.

## 1. API candidata por família

| Família | Tipo declarante | Assinatura catalogada | Estado |
|---|---|---|---|
| `FUNCTION_BLOCK` | `IScriptIecLanguageObjectContainer4` | `create_function_block(name, Guid? language?, string base_type?, string interfaces?)` | `NOVO` no MasterTool X (`docs/27` §7) |
| `FUNCTION` | `IScriptIecLanguageObjectContainer4` | `create_function(name, string return_type, Guid? language?)` | `NOVO` no MasterTool X (`docs/27` §7) |
| `DUT` (`STRUCT` e `ENUM`) | `IScriptIecLanguageObjectContainer` | `create_dut(name, DutType type?, string baseType?)` | `=`, assinatura idêntica à do 3.70 (`docs/27` §7) |

<caption>

**Como ler:** as três assinaturas vêm de reflexão estática sobre o assembly
instalado, não de teste em runtime — o mesmo grau de evidência que já
sustentou W1.1 e W1.2 antes de qualquer execução. `create_function_block` e
`create_function` são membros novos, específicos do MasterTool X;
`create_dut` já existia na geração anterior e não mudou.

</caption>

### ~~O parâmetro que ainda não foi medido: `DutType`~~ — CORRIGIDO em 2026-08-01

> **Esta seção estava errada, e o erro custou caro.** `DutType` **está**
> catalogado — no stub que o próprio produto versiona,
> `ScriptIecLanguageObjectContainer.pyi` L23: `Structure=1, Enumeration=2,
> Alias=3, Union=4`. A `run-031` (`docs/45`) mediu que ele é **injetado no
> escopo do script**, com os quatro membros conferindo com o stub.
>
> A lacuna era do **catálogo deste projeto**, e não da API — pela quarta vez.
> O texto original fica abaixo como registro do que foi afirmado e por quê.

`create_dut` aceita um `DutType type?` que decide se o objeto nasce `STRUCT`,
`ENUM`, `UNION` ou `ALIAS` (nomenclatura provável, não confirmada). ~~**Nenhum
dos valores do enum `DutType` está catalogado**~~ em `docs/27` nem em
`api/mastertool-api-observations.md` — a varredura ampla de `docs/27` §6
cobriu `IScriptIecLanguageObjectContainer` e o assembly `ScriptEngine3`
inteiro, e nenhum probe chegou a listar os membros do enum `DutType` em si.

```text
LACUNA — valores de DutType (STRUCT, ENUM, ...) nao catalogados
instrumento: reflexao estatica sobre o enum DutType em ScriptEngine3,
             equivalente ao que docs/27 §7 ja fez para PouType
bloqueante para: qualquer chamada de create_dut nesta trilha
```

Nenhum valor de `DutType` é suposto por analogia com `PouType`
(`Program`, `FunctionBlock`, `Function`, medido em `docs/27` §6). São enums
diferentes, de propósitos diferentes, e um nome de membro coincidente por
acaso não seria evidência.

### Guia de linguagem, herdado sem re-derivação

O `language?` de `create_function_block` e `create_function` é o mesmo
`Nullable<Guid>` já medido para `create_program` (`docs/27` §7): um `Guid`
tirado de `IScriptImplementationLanguages`, nunca uma string. Nada neste
contrato reabre essa medição — `docs/30` já a fechou, e a regra "a
linguagem não viaja como texto" vale idêntica para as três famílias novas.

## 2. Textos canônicos de nascimento

Três textos têm precedente **medido**, herdado sem re-derivação de `docs/31`:

| Objeto | Texto | SHA-256 | Observação |
|---|---|---|---|
| GVL | `{attribute 'qualified_only'}\nVAR_GLOBAL\nEND_VAR` | `fd27fd816bdf9d2116403f691bcb84694119b3553b1067619bb9b96dd310affb` | **com** pragma, **sem** quebra final |
| Declaração de `PROGRAM` | `PROGRAM PRG_AI_TESTE\nVAR\nEND_VAR\n` | `6a2401fa5915a354eae0895d290e4bb6d3483c4d3ca4e05cb7e5b230f4435841` | **com** quebra final |
| Implementação de `PROGRAM` | `""` (string vazia) | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` | é o SHA-256 da string vazia; vazio medido ≠ ausência de leitura |

<caption>

**Como ler:** os três hashes acima são os únicos hexadecimais de 64
caracteres permitidos neste documento — todos medidos em execução real
(`docs/31`), nenhum inventado. A GVL e o `PROGRAM` divergem justamente onde a
medição é mais fácil de errar por analogia: a GVL termina sem quebra de
linha, o `PROGRAM` termina com uma.

</caption>

### Para `FUNCTION_BLOCK`, `FUNCTION` e `DUT` não há medição

Nenhuma sessão real chamou `create_function_block`, `create_function` ou
`create_dut`. Não existe, portanto, texto canônico de nascimento medido para
nenhuma das quatro famílias-alvo deste contrato (`FB_AI_CONTADOR`,
`F_AI_SOMA`, `ST_AI_MOTOR`, `E_AI_ESTADO`).

```text
LACUNA — texto de nascimento de FUNCTION_BLOCK        nao medido
LACUNA — texto de nascimento de FUNCTION               nao medido
LACUNA — texto de nascimento de DUT STRUCT             nao medido
LACUNA — texto de nascimento de DUT ENUM               nao medido
instrumento: preflight de cada fase, sobre copia descartavel,
             medindo o texto ANTES de qualquer replace planejado
             (o mesmo metodo ja usado para GVL em docs/29 e PROGRAM em docs/30)
```

Preencher esses quatro textos por analogia com a GVL ou o `PROGRAM` seria
inventar. A GVL nasce com um pragma que o `PROGRAM` não tem; nada garante que
`FUNCTION_BLOCK` nasça com `VAR_INPUT`/`VAR_OUTPUT` vazios na mesma forma
sintática, que `FUNCTION` nasça com o tipo de retorno já escrito na
declaração da forma esperada, ou que um `DUT` `STRUCT`/`ENUM` nasça sem
nenhum corpo. Cada uma dessas quatro hipóteses só vira fato depois que o
preflight da fase correspondente medir o objeto recém-criado, antes de
qualquer escrita — exatamente o rito que `docs/30` já seguiu para o
`PROGRAM`.

## 3. Ordem de dependência entre as famílias

```text
DUT (STRUCT, ENUM)  ->  FUNCTION_BLOCK  ->  FUNCTION  ->  integracao (GVL + PROGRAM)
```

### DUT antes de quem o usa; FB antes de quem o instancia

Um `STRUCT` ou `ENUM` só existe como **tipo referenciável**; ele não tem
sentido próprio fora de uma declaração de variável que o use. Se o projeto de
integração precisar declarar uma variável do tipo `ST_AI_MOTOR` ou
`E_AI_ESTADO` — no `PROGRAM`, numa GVL, ou dentro de outro objeto —, o `DUT`
precisa existir na árvore antes que esse texto seja escrito, senão o
`replace` estaria referenciando um tipo inexistente (o mesmo raciocínio já
registrado em `docs/32` §3 para `create_gvl` antes de `create_program`).

Pelo mesmo motivo, um `FUNCTION_BLOCK` precisa existir antes de qualquer
código que declare uma **instância** dele (`FB_AI_CONTADOR` sendo usado como
tipo de uma variável `VAR fbContador : FB_AI_CONTADOR; END_VAR`, por exemplo,
no projeto de integração). Instanciar um FB que ainda não foi criado teria a
mesma classe de falha que referenciar uma GVL antes dela existir.

`FUNCTION_BLOCK` vem antes de `FUNCTION` neste plano por convenção de ordem
crescente de complexidade estrutural (uma FUNCTION_BLOCK carrega estado —
`VAR_OUTPUT` persistente entre chamadas — e uma FUNCTION não), não por
dependência real: nada nos quatro objetos-alvo da seção 5 faz `F_AI_SOMA`
depender de `FB_AI_CONTADOR`. Separar as fases nessa ordem só preserva a
disciplina de "uma família de cada vez" sem impor uma dependência que os
objetos-alvo não têm.

## 4. O que distingue cada família na árvore

### O `type_guid` de POU não distingue `PROGRAM` de `FUNCTION_BLOCK` de `FUNCTION`

Fato já medido e registrado (`docs/30` §"Identidade estrutural de PROGRAM",
`docs/32` §1): todo POU do projeto-base — `PROGRAM`, e por extensão qualquer
`FUNCTION_BLOCK` ou `FUNCTION` que venha a existir na mesma árvore —
compartilha o mesmo `type_guid` `6f9dac99-8de1-4efc-8465-68ac443b7d08`. Esse
GUID prova "isto é um POU"; não prova qual subtipo de POU.

### O discriminador que o verificador terá de usar no lugar

A varredura ampla de `docs/27` §6 já cobriu os 304 tipos públicos e ~1.544
membros de `ScriptEngine3` e dos plugins de scripting no MasterTool X, e
nenhum membro legível devolveu o subtipo de POU a partir do objeto já criado
— não há, hoje, um campo do tipo `IScriptObject.pou_kind` ou equivalente.
Isso não é uma lacuna de varredura incompleta; é o resultado de uma varredura
que já foi larga o bastante para cobrir esse tipo.

Na ausência de um campo legível, o discriminador que `docs/30` já adotou para
distinguir o `PROGRAM` recém-criado dos POUs preexistentes — e que este
contrato estende às três famílias novas — é a combinação de:

```text
nome exato do objeto            (PRG_AI_TESTE, FB_AI_CONTADOR, F_AI_SOMA, ...)
is_folder == False              is_transient_object == False
has_textual_declaration == True
procedencia registrada no journal da sessao:
    o objeto foi criado por ESTA chamada de create_function_block /
    create_function / create_program, nesta sessao — nunca por
    inspecao posterior de uma propriedade do objeto
```

Nenhum destes campos precisa de nova medição — todos já estão confirmados
para `PROGRAM` (`docs/30`) e a mesma API (`IScriptObject`,
`IScriptTextualObjectMarker`) é compartilhada por todo POU, sem distinção de
subtipo. O que fica como lacuna, e é diferente do discriminador em si, é
apenas o **texto** de nascimento de cada família (seção 2) — o
discriminador estrutural (nome + procedência de sessão) não depende dele.

### `DUT`: o discriminador é outro `type_guid`, também sem confirmação de subtipo

`docs/29` já mediu `type_guid` de GVL (`ffbfa93a-b94d-45fc-a329-229860183b1d`)
como distinto do de POU. Por analogia estrutural (não por suposição de
valor), é esperável que `DUT` tenha o seu próprio `type_guid`, distinto dos
dois anteriores — mas **esse valor não foi medido**, e a mesma pergunta da
seção 4 se repete dentro dele: mesmo que exista um `type_guid` de `DUT`
comum, nada garante que ele distinga `STRUCT` de `ENUM` internamente. Ver
lacuna de `DutType` na seção 1.

```text
LACUNA — type_guid de DUT                       nao medido
LACUNA — se type_guid de DUT distingue STRUCT/ENUM entre si   nao medido
```

### A linguagem NÃO é um discriminador verificável hoje

Achado registrado ao fechar W1.3B (2026-07-31): **não existe API catalogada
para LER a linguagem de um objeto já criado.** `language` aparece somente
como parâmetro de **entrada** de `create_pou`/`create_program`/
`create_function`/`create_function_block` (`docs/27` §7), e
`IScriptImplementationLanguages` só fornece um `Guid` **por linguagem**
(`st`, `ladder`, `fbd`, ...) — nunca o inverso, isto é, nenhum membro
catalogado devolve a linguagem **de** um objeto existente. Um probe chegou a
declarar `EXPECTED_ST_LANGUAGE_GUID` sem nunca a usar para ler de volta —
constante morta, que lia como cobertura sem cobrir nada.

Consequência direta para este contrato: **a linguagem não pode compor o
discriminador de família** (seção 4) nem qualquer critério de verificação
das fases da seção 6 — nenhum passo aqui depende de reler a linguagem de um
objeto após a criação. Isso é diferente de "a linguagem foi ST em todos os
objetos-alvo, então não precisa verificar" — é "não há como verificar isso
hoje, mesmo que se quisesse".

```text
LACUNA — existe alguma API read-only que devolva a linguagem de um objeto
  ja criado (equivalente inverso de IScriptImplementationLanguages)?
  nao encontrada na reflexao estatica ate agora; nao presumida ausente,
  apenas nao localizada
```

## 5. Objetos-alvo mínimos

Exatamente estes quatro objetos, mais o projeto de integração — nenhum outro
nome, nenhum outro campo:

| Objeto | Família | Corpo |
|---|---|---|
| `FB_AI_CONTADOR` | `FUNCTION_BLOCK` | `VAR_INPUT xIncrementa : BOOL; END_VAR` / `VAR_OUTPUT uiValor : UINT; END_VAR` — implementação `IF xIncrementa THEN uiValor := uiValor + 1; END_IF;` |
| `F_AI_SOMA` | `FUNCTION`, retorno `DINT` | `VAR_INPUT a, b : DINT; END_VAR` — implementação `F_AI_SOMA := a + b;` |
| `ST_AI_MOTOR` | `DUT STRUCT` | `xLiga : BOOL; xFalha : BOOL; rCorrente : REAL;` |
| `E_AI_ESTADO` | `DUT ENUM` | `Aguardando := 0, Executando := 1, Falha := 100` |

<caption>

**Como ler:** estes são os únicos quatro objetos autorizados a existir por
este contrato normativo. O texto do corpo é o que o **plano** de cada fase
deve escrever via `replace`, depois de o preflight medir o texto de
nascimento real (seção 2) — não é, em si, o texto de nascimento, que ainda é
lacuna.

</caption>

O projeto de integração usa os quatro objetos-alvo mais uma GVL e um
`PROGRAM` (o par já provado em W1.1–W1.4) e precisa compilar
(`build()`, offline, sem erro — o mesmo critério de `docs/32` §5) para ser
considerado concluído. Nenhum outro objeto entra nele.

## 6. Fase controlada por família, uma de cada vez

Cinco fases futuras, cada uma com allowlist mínima e literal, seguindo o
rito de `docs/28` §14:

```text
W2_DUT_STRUCT           create_dut, save_as
W2_DUT_ENUM             create_dut, save_as
W2_FUNCTION_BLOCK       create_function_block, save_as
W2_FUNCTION             create_function, save_as
W2_INTEGRATION          create_dut, create_function_block, create_function,
                        create_gvl, create_program, replace, save_as, build
```

### Por que nunca duas fases mutáveis abertas ao mesmo tempo

O desenho de fase única (`docs/28` §0, regra 4) existe exatamente para
impedir isto: se `W2_DUT_STRUCT` e `W2_FUNCTION_BLOCK` estivessem abertas na
mesma sessão, uma falha depois de `create_dut` e antes de `create_function_block`
deixaria ambígua a origem do problema — "o `DUT` falhou" e "o `FUNCTION_BLOCK`
falhou" deixariam de ser hipóteses distinguíveis, pelo mesmo motivo que
`docs/29` já registrou para não misturar `create_gvl` e `create_program` na
mesma sessão de prova. Cada fase desta seção autoriza **uma família**, na
ordem da seção 3, e a fase seguinte só abre depois que a anterior fechar,
aprovada, com commit isolado próprio (`docs/28` §14).

`W2_INTEGRATION` é a única exceção deliberada, e só porque ela testa
explicitamente a composição — o mesmo raciocínio que `docs/32` já usou para
justificar por que W1.4 reabre `create_gvl` e `create_program` juntos depois
de tê-los provado separadamente.

## 7. Tabela de fault injection

| Ponto de injeção | Estado esperado | Consequência sobre a cópia |
|---|---|---|
| falha antes de qualquer mutação (precondição) | `precondition_failed`, nenhuma API mutável chamada | cópia nunca é usada; descartada ou nem criada |
| falha após `create_dut` (STRUCT ou ENUM) | objeto já inserido na árvore em memória, nada persistido | cópia descartada inteira, sem tentar `remove` |
| falha após `create_function_block` | FB já inserido em memória | cópia descartada inteira |
| falha após `create_function` | FUNCTION já inserida em memória | cópia descartada inteira |
| falha no `replace` de declaração ou implementação de qualquer objeto | texto alterado em memória | cópia descartada inteira |
| falha em `save_as` | nenhum arquivo novo, ou arquivo parcial | cópia de trabalho e saída parcial descartadas |
| output criado mas reabertura falha | arquivo existe, sessão independente não consegue abri-lo | saída tratada como inválida; investigada, nunca reaberta à força |
| build com erro (só em `W2_INTEGRATION`) | `Severity` de erro presente na coleta de mensagens | sessão reprovada; avisos registrados na íntegra |
| diff inesperado (qualquer objeto ou texto fora do plano) | objeto ou texto não previsto pela seção 5/6 | sessão reprovada integralmente, mesmo que o resto do diff esteja correto |
| diálogo inesperado | qualquer diálogo fora do fluxo previsto | cancelado e registrado com o texto exato; sessão abortada |

<caption>

**Como ler:** toda linha desta tabela termina na mesma consequência —
"cópia descartada inteira" — e não por rigor excessivo: `create_*` devolve o
objeto **já inserido** na árvore, sem passo de confirmação, e não existe
rollback transacional na API do MasterTool X (`docs/27` §8, item 5;
`docs/32` §8). Não há como desfazer só o `create_function_block` e manter o
`create_dut` anterior — a unidade descartável é sempre o projeto inteiro, e é
por isso que nenhuma linha desta tabela aprova promoção parcial.

</caption>

### O instrumento que sustenta "diff inesperado", e o limite dele

A linha "diff inesperado" só é verificável na profundidade que o instrumento
de leitura alcançar, e os dois instrumentos catalogados **não alcançam a
mesma coisa**:

```text
get_children(False)   filhos DIRETOS de um nó, nao recursivo (docs/27 §9)
probes/21             varredura RECURSIVA, com limite de profundidade e de
                       nos configuraveis (docs/27 §4, docs/32 §7)
```

Um critério do tipo "nenhum outro objeto da família X foi alterado" só é
verificável **no nível do container imediato** se a verificação usar apenas
`get_children(False)` — objetos dois ou mais níveis abaixo do container onde
a fase escreve não entram nessa checagem. A tabela acima só sustenta essa
garantia na íntegra quando a verificação usa `probes/21` (varredura
recursiva já existente e versionada), não `get_children(False)` isolado.
Qualquer fase da seção 6 que declare "nenhum outro objeto foi tocado" como
critério de aceitação precisa citar `probes/21`, com o mesmo cuidado de
`docs/28` §9 sobre objeto transiente e `object_guid` instável.

## 8. O que cada diferença estrutural faz com o número de documentos a verificar

| Família | Declaração | Implementação | Documentos textuais a verificar |
|---|---|---|---|
| GVL | sim (o único) | não tem | **1** |
| `DUT` (`STRUCT`/`ENUM`) | sim (o único) | não tem — DUT não tem implementação | **1** |
| `PROGRAM` | sim | sim | **2** |
| `FUNCTION_BLOCK` | sim | sim | **2** |
| `FUNCTION` | sim (carrega o tipo de retorno na própria assinatura) | sim (o corpo atribui ao **nome da função**, não a uma `VAR` comum) | **2** |

<caption>

**Como ler:** a contagem da última coluna é exatamente o que separou W1.3A
(GVL, um documento — `docs/33`) de W1.3B (`PROGRAM`, dois documentos,
planejado em `docs/31`). Um `DUT` tem a mesma contagem que uma GVL, por não
ter implementação; `FUNCTION_BLOCK` e `FUNCTION` têm a mesma contagem que
`PROGRAM`, por terem as duas. A diferença entre elas não está em quantos
documentos existem, e sim no que cada documento contém — uma `FUNCTION` tem
tipo de retorno na declaração e um alvo de atribuição diferente na
implementação; um `FUNCTION_BLOCK` tem instância (uma variável declarada
alhures, do tipo do FB, fora do próprio objeto FB); um `DUT` não tem
implementação nenhuma para verificar.
</caption>

Consequência prática: verificar `ST_AI_MOTOR` e `E_AI_ESTADO` exige metade do
esforço de verificação textual de `FB_AI_CONTADOR` e `F_AI_SOMA` — um
documento contra dois, por objeto —, mas a instância de `FB_AI_CONTADOR`
(a variável que o projeto de integração declara para poder chamá-lo) abre
uma terceira verificação que não pertence ao objeto FB em si: ela mora no
documento de quem o instancia (o `PROGRAM` do projeto de integração), não no
`FUNCTION_BLOCK`.

## Limites

**O que a evidência já comprova, sem nova medição:**

- as três assinaturas de `create_function_block`, `create_function` e
  `create_dut` (seção 1), catalogadas por reflexão estática em `docs/27` §7;
- os três textos canônicos de GVL e `PROGRAM` (seção 2), medidos em runtime
  real em `docs/31`;
- que o `type_guid` de POU não distingue `PROGRAM`/`FUNCTION_BLOCK`/
  `FUNCTION` entre si (seção 4), e que a varredura ampla de `docs/27` §6 não
  encontrou nenhum campo legível que faça essa distinção;
- que não existe rollback transacional na API e que a unidade de descarte é
  sempre o projeto inteiro (seção 7), medido em `docs/27` §8 e aplicado em
  `docs/32` §8;
- que **não existe API catalogada para ler a linguagem de volta de um objeto
  já criado** (seção 4) — `language` só existe como parâmetro de entrada, e
  `IScriptImplementationLanguages` só converte nome→GUID, nunca o inverso;
- que `get_children(False)` só alcança filhos diretos, e que a verificação
  recursiva de árvore depende de `probes/21` (seção 7) — os dois instrumentos
  não são intercambiáveis.

**O que exige medição em campo, e que este documento não responde:**

- os valores do enum `DutType` (seção 1) — nenhum probe listou seus membros;
- os quatro textos de nascimento de `FUNCTION_BLOCK`, `FUNCTION`, `DUT
  STRUCT` e `DUT ENUM` (seção 2) — nenhuma sessão real chamou as três APIs
  novas nem `create_dut`;
- o `type_guid` de `DUT`, e se ele distingue `STRUCT` de `ENUM` entre si
  (seção 4);
- se existe, em alguma versão futura da superfície, um campo legível que
  distinga subtipos de POU diretamente no objeto — hoje a resposta é "não
  encontrado", que é diferente de "impossível";
- qualquer comportamento de `build()` especificamente sobre `FUNCTION_BLOCK`
  ou `FUNCTION` (por exemplo, mensagens de erro específicas de tipo de
  retorno ausente) — `docs/32` só validou `build()` sobre GVL e `PROGRAM`.

Nenhuma das lacunas acima foi preenchida por analogia. Cada uma está
registrada para ser fechada pelo preflight da fase correspondente (seção 6),
nunca por suposição neste contrato.

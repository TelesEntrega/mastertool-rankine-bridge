# Plano W1.3 — escrita textual controlada

Plano de execução e revisão do marco **W1.3**. Não normativo: quem manda é
[`28-contrato-escrita-controlada-mastertool-x.md`](28-contrato-escrita-controlada-mastertool-x.md).

**Este documento não abre gate nenhum.** `READ_ONLY_PHASE` continua `True`,
`CONTROLLED_WRITE_PHASE` continua `None`, e nenhuma operação mutável está
autorizada.

## Estado de referência

| | |
|---|---|
| Branch / `HEAD` | `main` / `d9896fe`, árvore limpa |
| W0 · W1.1 · W1.2 | encerrados e aprovados |
| Gate | `READ_ONLY_PHASE = True` · `CONTROLLED_WRITE_PHASE = None` |
| Runs preservadas | `run-001` a `run-006` |

## A decisão de rota: W1.3 não recria objetos

**Os artefatos aprovados de W1.1 e W1.2 são as entradas.** Recriar os objetos e
editar o texto na mesma sessão misturaria quatro capacidades — `create_gvl`,
`create_program`, `replace` e `save_as` — e uma falha depois da criação ficaria
ambígua: poderia estar na identidade do objeto, no acesso ao documento, no
conteúdo textual ou na persistência.

Como W1.1 e W1.2 já produziram artefatos validados, eles servem de **fixture
operacional** e deixam `IScriptTextDocument.replace` como única variável sob
teste.

```text
W1.3A   W1-A1.project  ->  editar GVL_AI_TESTE
W1.3B   W1-A2.project  ->  editar PRG_AI_TESTE
W1.4    projeto-base   ->  criar + escrever + build   (volta a integrar)
```

### A troca de base de 2026-07-31 não afeta W1.3, e afeta W1.4

O projeto-base passou a ser o `TemplateExemplo v1.project` **com cartões de I/O**
(`596625796e4efd54d3cc2d6286e858b683f0f58de66ab9a36eed532dd1d815f5`,
503.040 bytes) — ver `docs/29` §"Base nova".

**W1.3 não é afetado.** As suas entradas são `W1-A1` e `W1-A2`, saídas
congeladas e autocontidas, e o que se testa nelas é `replace`, não a base de
onde vieram. Fica registrado, sem esconder, que a **procedência delas é a base
anterior**, sem cartões de I/O.

**W1.4 é afetado**: ele parte do projeto-base, e o base é outro. Toda a baseline
estrutural — contagem de nós, `node_path` do `Application`, hash de estrutura —
precisa ser **remedida** por varredura read-only antes de W1.4. Em particular o
`node_path`: ele é caminho de índices, e cartões de I/O mudam a árvore sob o
`Device`.

## Os artefatos de referência, congelados

| | `W1-A1.project` | `W1-A2.project` |
|---|---|---|
| Origem | `run-003` (W1.1) | `run-006` (W1.2) |
| Tamanho | 287.824 bytes | 288.208 bytes |
| SHA-256 | `a0460e8272b8e48604daedaebe3c20776daa0fd949f4ebdb12d242460dbe0614` | `67092e58229a801badaba70bc8f097aecdabc3be5e86ad63ece52a8081a1e2a1` |
| Conteúdo além da baseline | `+ GVL_AI_TESTE` | `+ PRG_AI_TESTE` |
| Atributo | **somente leitura** | **somente leitura** |

Regras de uso, sem exceção:

```text
NUNCA abertos diretamente para alteracao
uma copia descartavel NOVA por run, em diretorio exclusivo
outputs sempre em arquivos DIFERENTES
divergencia de hash aborta ANTES de o MasterTool abrir
procedencia vinculada a run que comprovou a criacao
```

Eles não são dado industrial nem projeto de produção: são artefatos sintéticos
produzidos pelo próprio processo de validação, e é isso que os torna
utilizáveis como fixture.

## Os textos canônicos, medidos

Não presumidos. Reproduzidos aqui na forma exata, porque a forma exata é o que
a verificação compara.

### GVL, em `W1-A1.project`

```text
sha256   fd27fd816bdf9d2116403f691bcb84694119b3553b1067619bb9b96dd310affb
linhas   3
repr     "{attribute 'qualified_only'}\nVAR_GLOBAL\nEND_VAR"
```

### PROGRAM, em `W1-A2.project`

```text
declaracao   sha256 6a2401fa5915a354eae0895d290e4bb6d3483c4d3ca4e05cb7e5b230f4435841
             linhas 4
             repr   "PROGRAM PRG_AI_TESTE\nVAR\nEND_VAR\n"
implementacao sha256 e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855
             repr   ""      (string vazia)
```

### A assimetria que só a medição revela

**A GVL não termina em quebra de linha; o PROGRAM termina.** Três linhas contra
quatro, e a diferença está no `\n` final. A normalização já congelada ignora
**uma** quebra final na comparação, então isso não reprova nada — mas define o
que **escrever**, e um texto planejado que ignore a diferença deixa de espelhar
o envelope que o MasterTool produz.

O `e3b0c442…b855` da implementação é o SHA-256 da string vazia. Vale registrar
para que ninguém o confunda com "não foi possível ler": vazio medido e ausência
de leitura são estados diferentes.

## W1.3A — editar a GVL

Entrada: cópia descartável de `W1-A1.project`. Saída: `W1-A3-GVL.project`.

**Alvo único**, e nenhum outro objeto é tocado:

```text
nome        GVL_AI_TESTE
type_guid   ffbfa93a-b94d-45fc-a329-229860183b1d
container   Application  (root/1/0/0)
is_folder   False        is_transient  False
documento   textual_declaration   <- o UNICO permitido nesta fase
```

### Texto final planejado

```iecst
{attribute 'qualified_only'}
VAR_GLOBAL
    g_xTesteCriacao : BOOL;
END_VAR
```

```text
sha256  71f8079f6a8106315d4d5931ddd3fb247ad17c1fff374dbf6cdf79dd261a017c
linhas  4      sem quebra final, espelhando o envelope observado
```

Substitui o **documento inteiro**. Não inserir por posição, não criar um segundo
`VAR_GLOBAL`. A indentação de quatro espaços é escolha nossa e não tem efeito
sobre a API.

### Verificação

```text
pragma preservado EXATAMENTE uma vez
exatamente um VAR_GLOBAL      exatamente um END_VAR
exatamente uma declaracao     g_xTesteCriacao : BOOL;
nenhuma outra GVL alterada    nenhuma implementacao criada
nenhum objeto novo ou removido
```

## W1.3B — editar o PROGRAM

Entrada: cópia descartável de `W1-A2.project`. Saída: `W1-A3-PRG.project`.

```text
nome        PRG_AI_TESTE
type_guid   6f9dac99-8de1-4efc-8465-68ac443b7d08   (POU, medido em W1.2)
linguagem   ST, guid cc393387-a21c-4f68-a3e3-84c36951965d
container   Application  (root/1/0/0)
is_folder   False        is_transient  False
documentos  textual_declaration  E  textual_implementation
```

### Textos finais planejados

O envelope **preserva o cabeçalho** `PROGRAM PRG_AI_TESTE`, porque a medição de
W1.2 mostrou que ele faz parte do documento. Escrever apenas `VAR … END_VAR`
apagaria o cabeçalho; escrever um segundo o duplicaria.

Declaração:

```iecst
PROGRAM PRG_AI_TESTE
VAR
    xLocal : BOOL;
END_VAR
```

```text
sha256  6e4b13ab8010577533f0a25061cb285b6fe6288eb61494c4f80af26abdfa80f5
linhas  5      COM quebra final, espelhando o envelope observado
```

Implementação:

```iecst
xLocal := FALSE;
```

```text
sha256  313cdb1f7a9f98cd6a0b8c99d26f82402ba1aaa5c74ab8d1d9e6715e1347d517
```

`xLocal` **não referencia** `g_xTesteCriacao`: uma referência cruzada
acrescentaria resolução de símbolo à prova, e esta fase testa escrita textual.
A referência é assunto de W4.

### Verificação

```text
cabecalho PROGRAM PRG_AI_TESTE preservado, sem duplicacao
envelope VAR/END_VAR intacto        exatamente uma declaracao xLocal : BOOL;
implementacao exatamente xLocal := FALSE;
linguagem continua ST               nenhum outro PROGRAM alterado
nenhum objeto novo ou removido
```

## Operações mutáveis

**Somente duas**, e as mesmas nas duas fases:

```text
IScriptTextDocument.replace
IScriptProject.save_as
```

Proibidos, sem exceção: `create_gvl`, `create_program`, `create_pou`, `build`,
`save`, `insert`, `append`, `replace_line`, `rename`, `remove`, importação e
qualquer fallback.

`insert`, `append` e `replace_line` ficam de fora **de propósito**, embora
existam e pareçam convenientes: `replace` do documento inteiro é a única forma
cujo estado final não depende de offset, e portanto a única que se verifica
comparando um hash.

## Fases controladas

Duas fases **independentes**, com a mesma allowlist e alvos diferentes:

| Fase | Objeto permitido | Documento permitido |
|---|---|---|
| `W1_3A_EDIT_GVL` | `GVL_AI_TESTE` | `textual_declaration` |
| `W1_3B_EDIT_PROGRAM` | `PRG_AI_TESTE` | `textual_declaration` e `textual_implementation` |

Allowlist de ambas: `replace` e `save_as`.

**A existência de uma fase não autoriza a outra.** Cada uma exige commit
isolado de abertura e commit isolado de fechamento — e as duas nunca ficam
abertas ao mesmo tempo.

A restrição de **alvo** não vive no gate: o gate autoriza a operação, e o probe
carrega o nome do objeto e do documento como literais. São camadas diferentes,
e é por isso que duas fases com a mesma allowlist ainda são duas fases.

## Guardas adjacentes

Cada chamada mutável com a sua guarda na linha imediatamente anterior:

```python
safety.assert_controlled_write_allowed("replace")
text_document.replace(expected_full_text)
```

```python
safety.assert_controlled_write_allowed("save_as")
project.save_as(output_project_path)
```

Em W1.3B há **duas** chamadas de `replace`, cada uma com a sua guarda própria e
adjacente — declaração primeiro, implementação depois.

Sem wrapper genérico, sem `getattr`, sem reflexão, sem dispatch, e sem escolher
o documento a partir do nome da operação.

### O journal distingue o que a guarda não distingue

A operação de segurança é sempre o literal `replace`, mas o journal registra
qual documento foi alvo:

```text
replace_gvl_declaration
replace_program_declaration
replace_program_implementation
```

Sem isso, dois `replace` no journal de W1.3B seriam indistinguíveis, e o
registro deixaria de responder "qual documento falhou".

## Precondições comuns

Antes de qualquer `replace`:

```text
hash da entrada confere          copia exclusiva criada
output NAO existe                container unico
objeto-alvo unico                nome confere
type_guid confere                linguagem confere (quando aplicavel)
TEXTO INICIAL normalizado e exatamente o esperado
nenhum outro objeto difere da baseline
fase controlada correta          so replace e save_as autorizados
UI visivel                       usuario presente
nenhuma sessao online            nenhum dialogo
```

**Texto inicial divergente aborta.** Não adaptar o conteúdo automaticamente: se
o ponto de partida não é o esperado, o texto final planejado deixa de fazer
sentido, e "consertar na hora" produziria um resultado que ninguém revisou.

## Normalização

A regra já congelada em `docs/29`, sem alteração:

```text
CRLF e LF equivalentes
espaco em branco no fim de cada linha ignorado
UMA quebra de linha final ignorada
qualquer outra diferenca e DIVERGENCIA
```

SHA-256 preservados em quatro momentos, e não apenas no fim:

```text
texto inicial bruto      texto final planejado
texto apos o replace     texto apos a reabertura
```

## Verificação após cada `replace`, antes do `save_as`

```text
reler o documento e comparar com o texto planejado
confirmar que SOMENTE o documento autorizado mudou
zero objeto persistente adicionado ou removido
zero outro texto alterado
objetos transientes separados
```

Qualquer falha depois do primeiro `replace` **invalida a cópia integralmente**:
sem rollback interno, sem `save`, sem remoção, sem nova tentativa com conteúdo
diferente. Descartar é a única saída — é a mesma consequência de W1.1 e W1.2, e
pela mesma razão: não existe transação.

## Pós-save

```text
1. fechar o MasterTool
2. confirmar a ENTRADA intacta, por hash
3. calcular o hash da saida
4. reabrir a saida em execucao read-only independente
5. reler os documentos
6. comparar com os textos planejados
7. produzir diff textual e estrutural
8. confirmar nenhum objeto novo, removido ou renomeado
```

Diff permitido em **W1.3A**:

```text
~ textual_declaration de Application/GVL_AI_TESTE
```

Diff permitido em **W1.3B**:

```text
~ textual_declaration    de Application/PRG_AI_TESTE
~ textual_implementation de Application/PRG_AI_TESTE
```

Nada além disso. `.opt`, timestamps catalogados, GUIDs de sessão instáveis e
transientes de verdade são separados, nunca tratados como alteração
persistente.

## `build` não roda em W1.3

Fica em W1.4, depois que criação e escrita textual estiverem comprovadas
**separadamente**. Compilar aqui misturaria a prova de que o texto persistiu com
a prova de que o texto compila — e um erro de compilação num texto corretamente
persistido é um achado sobre o conteúdo, não sobre a capacidade de escrever.

## Ordem de execução

```text
1. W1.3A                    2. fechar o gate de W1.3A
3. W1.3B                    4. fechar o gate de W1.3B
```

Nunca as duas fases abertas ao mesmo tempo.

## Critérios de sucesso

**W1.3A**: exatamente uma chamada `replace`, exatamente uma `save_as`, pragma
preservado, variável global persistida após reabertura, nenhuma outra mudança.

**W1.3B**: exatamente **duas** chamadas `replace`, exatamente uma `save_as`,
declaração e implementação persistidas após reabertura, linguagem continua ST,
nenhuma outra mudança.

## Critérios de aborto

Antes de mutar:

```text
hash divergente              texto inicial divergente
objeto ausente ou duplicado  type_guid divergente
linguagem divergente         output existente
fase errada                  operacao adicional autorizada
dialogo                      projeto online
baseline estrutural divergente
```

Depois do primeiro `replace`: nenhuma tentativa de desfazer, nenhum `save`,
nenhuma remoção, nenhuma nova tentativa com conteúdo diferente — e descarte
integral da cópia.

## O que este plano não cobre

```text
build offline (W1.4)              integracao criacao + escrita (W1.4)
referencia cruzada entre objetos  resolucao de simbolo
FUNCTION, FUNCTION_BLOCK, DUT     task, device, biblioteca
Ladder e linguagem grafica        projeto existente ou de producao
```

# Plano W1.2 — criação de um `PROGRAM` ST vazio

> **ENCERRADO E APROVADO em 2026-07-31.** Executado em `run-004` (preflight),
> `run-005` (reprovada com segurança) e `run-006` (aprovada). Evidência completa
> em [`18-estado-e-proximo-passo.md`](18-estado-e-proximo-passo.md). O que segue
> é o plano como foi executado, com os resultados medidos incorporados.

> **BASE TROCADA em 2026-07-31**, depois deste marco: o projeto-base passa a ser
> o `TemplateExemplo v1.project` com cartões de I/O
> (`5966257…d815f5`). W1.2 foi executado sobre a base anterior, e o resultado
> continua válido — ele provou uma **capacidade**, não uma propriedade daquele
> arquivo. Os números estruturais citados aqui (`node_path root/1/0/0`, contagem
> de filhos do `Application`) são da base anterior e precisam ser **remedidos**
> antes de qualquer execução nova. Ver `docs/29` §"Base nova".

## Resultado medido

```text
GUID da linguagem ST   cc393387-a21c-4f68-a3e3-84c36951965d
                       medido no global ImplementationLanguages (probe 29)
type_guid do POU       6f9dac99-8de1-4efc-8465-68ac443b7d08
create_pou             disponivel, e NAO usado: create_program bastou
```

### O texto canônico, agora medido

```iecst
PROGRAM PRG_AI_TESTE
VAR
END_VAR
```

SHA-256 `6a2401fa5915a354eae0895d290e4bb6d3483c4d3ca4e05cb7e5b230f4435841`,
4 linhas; implementação vazia. **Sem pragma** e **sem comentário de cabeçalho** —
o comentário dos POUs do projeto-base vem do template Altus, não do objeto novo.
Era exatamente por isso que este plano proibia chamar o texto de um POU
preexistente de "canônico de um recém-criado".

### O GUID não viaja como texto

Achado da `run-005`: `create_program` recusa string com
`TypeError: expected Nullable[Guid], got str`. O plano só transporta texto — JSON
não tem tipo `Guid` — então a conversão via `System.Guid` acontece na fase de
**precondição**, antes da guarda. Falha de conversão é `precondition_failed`,
nunca `create_program_failed`.


Plano de execução e revisão do marco **W1.2**. Não normativo: quem manda é
[`28-contrato-escrita-controlada-mastertool-x.md`](28-contrato-escrita-controlada-mastertool-x.md).
Onde este plano e o contrato divergirem, o contrato prevalece.

**Este documento não abre gate nenhum.** `READ_ONLY_PHASE` continua `True`,
`CONTROLLED_WRITE_PHASE` continua `None`, e **nenhuma operação mutável está
autorizada**.

## Estado de referência

| | |
|---|---|
| Branch / `HEAD` | `main` / `a3cdc21`, árvore limpa |
| W0 · W1.1 | encerrados e aprovados |
| Gate | `READ_ONLY_PHASE = True` · `CONTROLLED_WRITE_PHASE = None` |
| Projeto-base | projeto sintético mínimo com controlador NX3008 |
| Entrada de W1.2 | **o projeto-base**, nunca `W1-A1.project` |

Reusar a saída de W1.1 misturaria a prova de criação de GVL com a de criação de
POU. A subdivisão existe justamente para mantê-las separadas: se W1.2 falhasse
sobre um projeto que já contém uma GVL criada por script, não saberíamos qual
das duas capacidades produziu a falha.

## Objetivo

```text
1. criar exatamente UM objeto PROGRAM, de nome PRG_AI_TESTE
2. linguagem ST definida por GUID, nunca por string
3. persistir exclusivamente por save_as, em W1-A2.project
4. reabrir de forma independente
5. diff estrutural de exatamente um PROGRAM ST
6. NENHUMA edicao textual
```

O passo 6 é o ponto do marco. A declaração e a implementação que o MasterTool
gerar sozinho são **lidas e preservadas**, nunca substituídas: manter a prova de
criação separada da prova de edição é o que permitirá, em W1.3, atribuir uma
falha a uma das duas.

> **A criação W1.2 não chama `replace`.** Declaração e implementação geradas
> automaticamente pelo MasterTool são apenas lidas e preservadas.

## A correção conceitual que este plano incorpora

O texto padrão de um `PROGRAM` **recém-criado não é descobrível antes da
criação**. O preflight consegue provar a API, o GUID de ST, a identidade
estrutural dos PROGRAMs existentes e a interface textual — e nada além disso.

O conteúdo padrão exato do objeto novo será medido **depois de
`create_program` e antes de `save_as`**, exatamente como o texto canônico da
GVL foi medido em W1.1. Ler a declaração de um PROGRAM **preexistente** é
evidência auxiliar; chamá-la de "canônico de um objeto novo" seria uma
conclusão que a medição não sustenta.

O artefato do probe 29 carrega essa ressalva num campo próprio
(`canonical_text_note`), e há teste que falha se ela sumir. A ressalva no
artefato vale mais do que a ressalva no documento: é ela que acompanha a
evidência quando alguém a ler daqui a um ano.

## A API de criação

Assinatura medida por reflexão estática em `docs/27` §7:

```text
IScriptIecLanguageObjectContainer4.create_program(
    String name,
    Nullable<Guid> language?        <- OPCIONAL
) -> IExtendedObject<IScriptObject>
```

Dois argumentos, o segundo opcional, retorno no mesmo envelope que o resto do
projeto já manipula. `create_program` é **novo no MasterTool X** — não existe
em 3.70.

**A linguagem será sempre passada explicitamente**, embora o parâmetro seja
opcional: omiti-la deixaria o MasterTool escolher o padrão, e "o padrão hoje é
ST" é suposição, não medição.

### `create_pou` fica PROIBIDA em W1.2

O reconhecimento registra se a sobrecarga antiga
(`create_pou(name, PouType, Guid?, ...)`) também está disponível, **sem
invocá-la e sem autorizá-la**. A regra:

```text
create_program disponivel e com assinatura suficiente
    -> create_pou PROIBIDA em W1.2
create_program ausente ou insuficiente
    -> PARAR. Revisar este contrato ANTES de abrir qualquer gate.
```

Nunca as duas na mesma fase, e **nunca fallback na mesma sessão**: tentar a
segunda quando a primeira falha transforma uma sessão de prova em sessão de
tentativa e erro, e o resultado deixa de dizer qual API funciona.

## O GUID da linguagem ST

`IScriptImplementationLanguages.st` é uma propriedade `Guid`, somente leitura.
**Nenhum membro dos assemblies catalogados devolve
`IScriptImplementationLanguages`** — ela só pode vir de um global injetado pelo
ScriptEngine, e o nome desse global **não está catalogado**.

O probe 29 resolve isso por medição, não por suposição:

```text
lista LITERAL e fechada de candidatos     (mesma forma aprovada em probes/15)
   implementation_languages
   ImplementationLanguages
   languages
+ registro dos NOMES dos globais efetivamente injetados
```

Se nenhum candidato resolver, o estado é `st_language_guid_missing` **e os
nomes observados vão no artefato** — é a pista para o próximo slice, em vez de
um beco sem saída.

Dois limites que o plano fixa:

- **a string `"ST"` nunca substitui o GUID.** O parâmetro é `Nullable<Guid>`;
  passar texto seria inventar API;
- **não hardcodar GUID vindo só de documentação.** O valor tem de sair do
  runtime. Um GUID copiado de documento e nunca confirmado é exatamente o tipo
  de suposição que já custou um preflight nesta trilha.

`online` e `device_repository` ficam **fora** dos candidatos: eles podem
iniciar comunicação só de terem propriedade lida
(`common/compatibility.py`: `SIDE_EFFECT_RISK`).

## Identidade estrutural de PROGRAM

Medida sobre os PROGRAMs que já existem no projeto-base, read-only:
`type_guid`, `is_folder`, `is_transient_object`, presença de
`textual_declaration` e `textual_implementation`, nome e posição.

Da varredura de W0, os quatro POUs do projeto-base compartilham:

```text
type_guid  6f9dac99-8de1-4efc-8465-68ac443b7d08
           MainPrg, SpecialVariablesPrg (SystemPOUs)
           StartPrg, UserPrg            (UserPOUs)
```

**Critério principal: o `type_guid` medido em runtime**, não heurística
textual — a mesma correção que W1.1 impôs para a GVL.

### Uma limitação que o plano declara em vez de esconder

Esse GUID identifica **POU**, e um `FUNCTION_BLOCK` ou uma `FUNCTION` podem
compartilhá-lo. Ele prova "é um POU", não "é um `PROGRAM`". O preflight mede o
que existe; se nenhum membro comprovado distinguir o subtipo, a distinção fica
como **lacuna declarada**, e a verificação de W1.2 se apoia em:

```text
type_guid de POU        +  nome exato PRG_AI_TESTE
is_folder == False      +  is_transient == False
has_textual_declaration == True
o objeto foi criado por create_program, e nao por outra API
```

Inventar um discriminador que não foi medido seria pior do que declarar a
lacuna.

### O trap do nome duplicado

`MainPrg` aparece **duas vezes** na árvore do projeto-base:

```text
root/1/0/0/1/0     MainPrg   type 6f9dac99...   <- o POU
root/1/0/0/3/0/0   MainPrg   type 413e2a7d...   <- referencia de chamada na task
```

Busca por nome encontraria os dois. É mais uma razão concreta para o container
e os objetos virem por **caminho de índices**, e para o preflight abortar com
`container_ambiguous` quando mais de um irmão casa com a identidade esperada.

## Conteúdo textual de PROGRAMs existentes

Lidos sem alterar, e classificados por vocabulário fechado:

```text
vazio_total                 declaracao e implementacao vazias
somente_declaracao          implementacao vazia
somente_implementacao       declaracao vazia
declaracao_e_implementacao  ambas com conteudo
texto_ilegivel              nao foi possivel ler
```

Se algum PROGRAM preexistente for `vazio_total`, o seu texto entra como
**evidência auxiliar** — e ainda assim não é "o canônico de um objeto novo".
Os POUs do projeto-base vêm de template Altus e provavelmente têm conteúdo;
isso é medição, não previsão.

## Estados do preflight

Vocabulário fechado. **Somente `preflight_passed` permite preparar o gate.**

```text
preflight_passed                      0
container_not_found                   2
container_ambiguous                   2
target_name_exists                    2
create_program_member_missing         2
create_program_member_not_callable    2
st_language_guid_missing              3
st_language_guid_ambiguous            3
program_identity_unresolved           3
runtime_mismatch                      2
fatal                                 1
```

## A futura mutação

### Precondições

```text
nova copia do projeto-base            output W1-A2.project inexistente
PRG_AI_TESTE ausente                  container unico
create_program diretamente disponivel GUID ST confirmado em runtime
identidade do runtime correta         nenhuma fase concorrente ativa
usuario presente                      UI visivel
projeto offline por procedimento operacional
```

### As únicas mutações

Guardas imediatamente adjacentes, nome literal no código:

```python
safety.assert_controlled_write_allowed("create_program")
created_program = iec_container.create_program("PRG_AI_TESTE", st_language_guid)
```

```python
safety.assert_controlled_write_allowed("save_as")
project.save_as(output_project_path)
```

`st_language_guid` chega **resolvido em runtime**, medido antes. A assinatura
final se ajusta à API real: se a medição mostrar forma diferente da catalogada,
o contrato é revisado antes da abertura do gate — **não se inventa parâmetro**.

### Verificação em memória, antes do `save_as`

```text
retorno nao nulo                 nome PRG_AI_TESTE
type_guid de POU                 linguagem ST
exatamente UM persistente novo   zero GVL novas
zero FUNCTION, FUNCTION_BLOCK, DUT, pasta ou task novos
declaracao automatica REGISTRADA (o canonico de W1.2)
implementacao automatica REGISTRADA
nenhum replace
```

Qualquer divergência bloqueia o `save_as`, invalida a cópia inteira e exige
descarte integral. Sem `remove`, sem `rename`, sem retry, sem rollback interno
— não existe rollback transacional.

### Pós-save

Reabrir de forma independente e confirmar:

```text
exatamente um PRG_AI_TESTE       tipo POU pelo type_guid medido
linguagem ST                      textos IGUAIS aos observados antes do save,
                                  sob a normalizacao ja fixada em docs/29
nenhum outro objeto alterado
```

Diff permitido, e nada além:

```text
+ 1 objeto persistente
  nome: PRG_AI_TESTE
  tipo: PROGRAM (type_guid de POU medido)
  linguagem: ST
  container: Application
```

Reprovam a sessão: outra GVL, outro POU, DUT, pasta, task, device, library,
alteração textual em objeto preexistente, mudança de compiler version, ou hash
do output diferente do registrado após o `save_as`. `.opt`, timestamps
catalogados, GUIDs de sessão instáveis e transientes de verdade são separados,
**nunca** tratados como alteração persistente.

## O gate futuro

Fase isolada, em commit próprio, com os testes estruturais junto
(`docs/28` §14):

```text
CONTROLLED_WRITE_PHASE = "W1_2_CREATE_PROGRAM"
allowlist maxima        = create_program, save_as
```

`create_pou` **só** entra se o reconhecimento provar que `create_program` não
basta — e, nesse caso, este contrato é revisado **antes** da abertura.

Continuam proibidos, sem exceção: `create_gvl` (a fase de W1.1 está encerrada),
`replace`, `build`, `save`, tasks, Program Calls, devices, libraries,
importação, `rename`, `remove` e qualquer fallback de API.

## Execução read-only futura

Sessão nova — `run-004` —, exclusivamente read-only, preservando `run-001`,
`run-002` e `run-003`:

```text
nova copia descartavel        hash antes e depois
.opt confinados               artefato de conclusao
nenhum mutador executado      parar ANTES de abrir a fase W1.2
```

## O que este plano não cobre

```text
edicao textual (W1.3)          build offline (W1.4)
FUNCTION e FUNCTION_BLOCK      DUT, enum, struct, PersistentVars
task e Program Call            biblioteca, device, hardware
Ladder e linguagem grafica     projeto existente ou de producao
```

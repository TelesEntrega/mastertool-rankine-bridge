# Plano W1 — primeira mutação controlada no MasterTool X

Plano de execução e revisão do marco **W1**. Documento **não normativo**: quem
manda é [`28-contrato-escrita-controlada-mastertool-x.md`](28-contrato-escrita-controlada-mastertool-x.md).
Onde este plano e o contrato divergirem, o contrato prevalece e o plano está
errado.

**Este documento não abre gate nenhum.** A fase `W1_1_CREATE_GVL` foi
autorizada à parte, em `b8ad7bb`; `READ_ONLY_PHASE` permanece `True` e nenhuma
linha de código de escrita existe ainda.

## Estado de referência

| | |
|---|---|
| Branch / `HEAD` | `main` / `bd5e8fd`, árvore limpa |
| MasterTool X | `MT9000.exe` **4.1.0.11**, instalação `C:\Program Files\Altus\MT9000 4.1.0\` |
| ScriptEngine | **4.2.0.0** (medido no assembly carregado) |
| IronPython | **2.7.12**, `sys.platform` `cli` |
| Arquitetura | 64 bits **comprovado em runtime** (`IntPtr.Size = 8`) |
| Probes read-only | compatíveis, rodaram sem alteração (`docs/27` §9) |
| Contrato | `docs/28`, escrito e commitado |
| Gate de escrita | `READ_ONLY_PHASE = True` — **sempre**; exceção nomeada `CONTROLLED_WRITE_PHASE = "W1_1_CREATE_GVL"`, autorizando `create_gvl` e `save_as` (`b8ad7bb`) |

## Por que W1 é subdividido

Criar GVL, criar POU e escrever texto numa execução só resolveria em um passo
e deixaria a falha ambígua: um erro no final não diria se a criação, a seleção
de linguagem ou a escrita textual foi a causa. Pior, `create_*` **já insere o
objeto na árvore** — uma falha tardia deixaria um projeto meio alterado sem
dizer qual capacidade falhou.

Então: **uma execução, uma capacidade nova.** Cada fase reusa o que a anterior
já provou, e a última refaz tudo do zero como prova de integração.

```text
W1.1  criar GVL vazia                    <- prova: criacao de objeto
W1.2  criar PROGRAM ST vazio             <- prova: criacao tipada + linguagem por GUID
W1.3  escrever declaracao e implementacao<- prova: escrita textual
W1.4  sequencia completa + build + diff  <- prova: integracao e persistencia
```

### Encadeamento das entradas

| Fase | Entrada | Saída |
|---|---|---|
| W1.1 | cópia nova do projeto-base | `A1` |
| W1.2 | cópia nova de **`A1`** | `A2` |
| W1.3 | cópia nova de **`A2`** | `A3` |
| W1.4 | cópia nova do **projeto-base** | `A4` |

Encadear é legítimo porque, quando W1.2 roda, a criação de GVL **já é
capacidade aprovada** — deixou de ser a variável sob teste. E W1.4 recomeça do
projeto-base justamente para que a prova de integração não dependa de nenhum
artefato intermediário.

Isto não contradiz `docs/28` §2: o que é reaproveitado é o **artefato de saída
verificado** da fase anterior, nunca a cópia de trabalho de outra sessão. Cada
fase faz a sua própria cópia, com hash conferido antes.

## Projeto de teste

> **BASE TROCADA em 2026-07-31.** O projeto-base passa a ser o `TemplateExemplo v1.project`
> **com cartões de I/O configurados**. Toda a medição da seção seguinte foi
> feita sobre a base anterior e **não vale mais**: ver §"Base nova" logo abaixo
> antes de usar qualquer número daqui.

### Base nova — a partir de 2026-07-31

| | |
|---|---|
| Arquivo | `TemplateExemplo v1.project`, na pasta de origem do usuário |
| Tamanho | **503.040 bytes** (a base anterior tinha 287.152) |
| SHA-256 | `596625796e4efd54d3cc2d6286e858b683f0f58de66ab9a36eed532dd1d815f5` |
| Modificado | 2026-07-31 14:13 |
| Diferença | **cartões de I/O configurados** pelo usuário |

**Classificação anterior aposentada.** "Projeto sintético mínimo com controlador
NX3008" descrevia um projeto sem I/O; com os cartões, a descrição correta é
**projeto sintético com controlador NX3008 e cartões de I/O configurados**.

#### O que precisa ser REMEDIDO antes de qualquer execução

Nada abaixo foi verificado na base nova, e **presumir continuidade seria o erro
que este projeto não comete**:

```text
contagem de raizes            (era 3)
contagem de nos               (era 34)
hash deterministico da estrutura   (era b2825550...1c22c)
node_path do Application      (era root/1/0/0)   <- o mais critico
type_guid do Application      (era 639b491f-...)
```

O `node_path` é o mais crítico: ele é **caminho de índices**, e acrescentar
cartões de I/O muda a árvore sob o `Device`. Se um índice deslocar, `root/1/0/0`
deixa de apontar para o `Application` — e o preflight abortaria com
`container_not_found`, que é o comportamento certo, mas por um motivo evitável.

**Antes de qualquer sessão nova**: varredura read-only com `probes/21` sobre uma
cópia descartável, e só então recongelar os números acima.

#### O que NÃO é afetado

Os artefatos `W1-A1.project` e `W1-A2.project` continuam válidos como fixtures
de W1.3. Eles são **saídas congeladas e autocontidas**, e o que W1.3 testa neles
é `replace` — não a base de onde vieram. Fica registrado, sem esconder, que a
**procedência deles é a base ANTERIOR**: foram gerados de um projeto sem cartões
de I/O.

W1.4, que parte do projeto-base, passa a partir da **base nova**.

---

## Histórico: a base anterior (sem cartões de I/O)

A seção abaixo descreve a base usada em W1.1 e W1.2, e vale como registro do
que foi medido então — não como configuração corrente.

Classificação de então: **projeto sintético mínimo com controlador NX3008**.
**Ele não era um "projeto vazio"**, e chamá-lo assim seria descrever errado a
superfície do diff.

```text
projeto sintetico minimo com controlador NX3008
```

É aceitável como base de W1 porque foi criado especificamente para o ensaio,
não contém lógica nem dados de cliente, não tem escravos de fieldbus, tem um
`Application` real para receber a GVL, não exige ampliar a allowlist com
criação de projeto, e é usado **somente por cópia descartável**.

O que ele contém — e que é **baseline imutável**, não detalhe incidental:

```text
Device NX3008 com COM 1, NET 1..3 e CAN     (nenhum escravo de fieldbus)
Plc Logic > Application
  Library Manager
  SystemPOUs   MainPrg, SpecialVariablesPrg
  UserPOUs     StartPrg, UserPrg
  UserGVLs     Qualities, ReqDiagnostics, Disables
  SystemGVLs   System_Diagnostics, Module_Diagnostics, IOQualities,
               Special_Variables
  Task Configuration > MainTask > MainPrg
  Bill of Materials, Configuration and Consumption
Project Settings                            __VisualizationStyle
```

POUs e GVLs padrão **não são alvo e não são ruído**: qualquer alteração ou
desaparecimento deles **reprova a sessão**.

**Nenhuma criação de projeto pela API em W1.** Criar um projeto realmente
vazio exigiria `ScriptProjects.create`, que não está na allowlist — e ampliar a
allowlist para preparar um ensaio inverteria a ordem entre autorização e uso.

### Baseline congelada — da base ANTERIOR, superada em 2026-07-31

Registrada no plano real, sob `input_project.baseline`. **Estes números valem
para a base sem cartões de I/O** e estão preservados como registro do que W1.1 e
W1.2 mediram:

| | |
|---|---|
| SHA-256 do projeto-base | `6183d01dcae9091a531a698afe794a3cbbf8f7882c921a67aeecfa9db5540dd3` |
| Raízes | **3** |
| Nós | **34** |
| `node_path` do Application | `root/1/0/0` |
| Nome esperado | `Application` |
| `type_guid` esperado | `639b491f-5557-464c-af91-1471bac9f549` |
| Hash determinístico da estrutura | `b2825550bca6a69aab9a39a970c66dad5cddb475a284111793d119a180b1c22c` |

O hash de estrutura é sobre `node_id \| name \| type_guid` de cada nó,
ordenados por `node_id`, medidos pela varredura read-only do `probes/21`.
**`object_guid` fica de fora de propósito**: ele não é estável entre sessões
(`docs/22`), e incluí-lo faria o hash mudar sem que o projeto mudasse.

**Qualquer divergência aborta antes do preflight.** Na prática quem faz cumprir
isso é o SHA-256 do arquivo, conferido pelo wrapper antes de qualquer abertura:
bytes iguais implicam estrutura igual. As contagens e o hash de estrutura são o
congelamento legível — servem para revisão humana e para a comparação
pós-`save_as`, não substituem o hash do arquivo.

### Regras que continuam valendo

```text
projeto-base SOMENTE LEITURA   uma copia descartavel POR EXECUCAO
diretorio EXCLUSIVO por execucao (o IDE cria .opt irmaos)
todas as saidas fora do repositorio, em caminho SEM espaco
sem conexao configurada com CLP, sem biblioteca externa acrescentada
```

O diretório é exclusivo por execução porque abrir um projeto cria
`<nome>-AllUsers.opt` e `<nome>-<usuario>-<maquina>.opt` (medido, `docs/27` §9).
Confinar esses arquivos é o que permite afirmar que nada escapou.

Caminho sem espaço continua obrigatório: o `--scriptargs` quebra o valor em
espaço em branco, medido no MasterTool X.

### O diff permitido, dito uma vez

```text
+ GVL_AI_TESTE
```

Um objeto persistente, com forma de GVL, com esse nome, no container
selecionado. **Nada mais.** Alteração ou desaparecimento de qualquer objeto
preexistente da baseline reprova a sessão — os POUs e GVLs padrão do esqueleto
NX3008 entram nessa conta.

### Registro obrigatório por execução

```text
SHA-256 do projeto-base                 SHA-256 da copia, antes
instalacao exata do MasterTool          versao do ScriptEngine (assembly carregado)
plano de alteracao e seu hash           identificador da execucao
caminho do arquivo de saida             SHA-256 de tudo, depois
```

### O container IEC vem do caminho, não do nome

O alvo de `create_gvl`/`create_program` é o objeto que implementa
`IScriptIecLanguageObjectContainer` — tipicamente a Application. Ele é
localizado **antes**, pela varredura read-only do `probes/21`, e o plano carrega
o **caminho de índices** (`root/1/1/0`), não o nome.

Nome não serve como identidade: depende do idioma e do encoding do projeto, e o
mesmo nome se repete em ramos diferentes (`docs/23`). Se a varredura encontrar
zero ou mais de um candidato, **aborta** — container ambíguo é critério de
aborto, não coisa a resolver por heurística.

## W1.1 — criação de GVL vazia — **ENCERRADA E APROVADA** em 2026-07-31

Executada em três runs (`run-001` reprovada com segurança por defeito do probe,
`run-002` preflight aprovado, `run-003` mutação aprovada). Evidência completa em
[`18-estado-e-proximo-passo.md`](18-estado-e-proximo-passo.md). O que segue
abaixo é o plano como foi executado, mantido como registro.

### Identidade de GVL — critério corrigido pela medição

O plano original verificava a forma estrutural porque não havia identidade
medida. Agora há:

| Ordem | Critério |
|---|---|
| **principal** | `type_guid == ffbfa93a-b94d-45fc-a329-229860183b1d` |
| | nome esperado `GVL_AI_TESTE` |
| | `is_folder == False` · `is_transient == False` · `has_textual_declaration == True` |
| **fallback** | `has_textual_declaration and not is_folder` — evidência auxiliar, conservadora, **nunca identidade definitiva** |

O GUID é o mesmo das GVLs preexistentes do projeto-base, o que o torna
verificável contra a própria baseline em vez de contra uma suposição.

**Única mutação permitida:** `create_gvl("GVL_AI_TESTE")`, com o nome literal,
sobre o container identificado por caminho.

### A guarda fica colada na chamada

Cada operação mutável carrega a sua própria guarda, **imediatamente antes da
invocação real**:

```python
safety.assert_controlled_write_allowed("create_gvl")
nova_gvl = container.create_gvl("GVL_AI_TESTE")
...
safety.assert_controlled_write_allowed("save_as")
project.save_as(caminho_saida)
```

**A função é `assert_controlled_write_allowed`, não `assert_operation_allowed`.**
A guarda legada desvia toda operação mutável do MasterTool X para a porta única
e levanta mesmo para as duas autorizadas — chamá-la ali faria o probe abortar
sempre. Uma porta, um nome.

Validar a fase só uma vez, no início do script, **não basta**: deixaria todo o
corpo implicitamente autorizado, e a distância entre a verificação e a chamada é
exatamente onde uma operação a mais passa despercebida numa revisão.

**Nada de wrapper genérico** que receba o nome da operação por parâmetro e
despache. Um `executar(nome_da_operacao)` recria o acoplamento dinâmico que a
allowlist existe para impedir: o nome vem escrito, literal, na linha de cima da
chamada.

### O que o manifesto registra por operação

```text
fase controlada observada (CONTROLLED_WRITE_PHASE lido em runtime)
operacao solicitada, como texto literal
resultado da autorizacao (autorizada / recusada, com a mensagem)
arquivo e linha logica da chamada guardada
confirmacao de que NENHUMA outra operacao mutavel foi solicitada
```

O último item é afirmação verificável, não promessa: o probe declara a lista das
operações que solicitou, e ela tem de bater com a allowlist da fase — duas
solicitações onde a fase autoriza duas, e nenhuma a mais.

Proibido nesta fase: criar POU, escrever qualquer texto, criar pasta, renomear,
remover, compilar, e `save()` sobre a entrada.

### Depois da criação, tudo read-only

1. inspecionar a árvore **em memória** e confirmar **exatamente uma** GVL nova;
2. **ler a declaração textual que o próprio IDE gerou** para a GVL vazia — ver
   §"A pergunta que W1.1 e W1.2 respondem";
3. `save_as` para arquivo **novo** (`A1`), que não pode existir antes;
4. fechar sem salvar de novo;
5. **reabrir `A1`** e verificar existência, nome e tipo da GVL;
6. materializar pelo caminho read-only (export / varredura);
7. confirmar que **nenhum outro objeto persistente** apareceu.

O passo 5 é o que separa "o objeto existiu na sessão" de "o objeto foi
persistido". Sem reabrir, a prova não vale.

## W1.2 — criação de PROGRAM ST vazio

Só depois de W1.1 aprovado. Entrada: cópia de `A1`.

**Única criação permitida:**

```text
create_program("PRG_AI_TESTE", <guid_st>)
```

O GUID vem de `IScriptImplementationLanguages.st`, lido em runtime. **A string
`"ST"` não é aceita como linguagem** — o parâmetro é `Guid?`, e passar texto
seria inventar API.

Se a interface real exigir a sobrecarga antiga
(`create_pou(name, PouType.Program, <guid_st>, ...)`), ela **já está catalogada**
(`docs/27` §7) e pode substituir a chamada — mas a escolha entra no plano JSON
antes da execução, nunca durante.

### Verificação

```text
tipo PROGRAM confirmado         linguagem ST confirmada pelo GUID, nao pelo nome
save_as -> A2, arquivo novo     reabrir e verificar estruturalmente
ausencia de implementacao nao prevista
ler a declaracao gerada pelo IDE para o PROGRAM vazio
```

## RESPONDIDO em 2026-07-31 — o texto canônico da GVL vazia

A pergunta abaixo foi **respondida por leitura**, na `run-003`, sem escrever
nada. O documento que o próprio MasterTool gerou para a GVL recém-criada:

```iecst
{attribute 'qualified_only'}
VAR_GLOBAL
END_VAR
```

SHA-256 textual
`fd27fd816bdf9d2116403f691bcb84694119b3553b1067619bb9b96dd310affb`, 3 linhas.

```text
o documento contem o BLOCO COMPLETO, nao so o corpo interno
o pragma {attribute 'qualified_only'} e gerado pelo MasterTool, nao foi pedido
```

Consequência direta, e não era o que o plano supunha: **substituir apenas por
`VAR_GLOBAL … END_VAR` apagaria o pragma**, e **inserir outro `VAR_GLOBAL`
dentro do documento aninharia o bloco**. Qualquer uma das duas produziria um
erro que só apareceria no build, longe da causa.

### Conteúdo de W1.3, corrigido

O `replace` substitui o **documento inteiro** por esta forma, preservando o
envelope canônico:

```iecst
{attribute 'qualified_only'}
VAR_GLOBAL
    g_xTesteCriacao : BOOL;
END_VAR
```

A comparação pós-save de W1.3 deve confirmar:

```text
pragma preservado
exatamente UM bloco VAR_GLOBAL
exatamente UMA declaracao g_xTesteCriacao : BOOL;
nenhuma alteracao em outra GVL
```

**W1.3 não está autorizado por este registro.** O texto acima é o conteúdo
corrigido para quando a fase for aberta, não uma autorização.

## A pergunta original, mantida como registro do método

**Não sabíamos qual forma textual a API espera.** O `IScriptTextDocument` de uma
GVL pode conter o bloco inteiro (`VAR_GLOBAL … END_VAR`) ou apenas o corpo
interno, com o editor desenhando o invólucro. O mesmo vale para o cabeçalho
`PROGRAM PRG_AI_TESTE` na declaração de um POU.

Escrever texto sem saber disso produziria `VAR_GLOBAL` aninhado dentro de
`VAR_GLOBAL`, ou um POU sem cabeçalho — e o erro só apareceria no build, longe
da causa.

A resposta **não exige escrita**: basta **ler** `textual_declaration` do objeto
vazio que o próprio MasterTool acabou de criar, em W1.1 e W1.2. O que o IDE
gera é a forma canônica. Esse texto vai para o registro da execução e **define**
o conteúdo de W1.3.

Se a leitura devolver vazio ou algo inesperado, W1.3 **não começa** — vira
achado, e o conteúdo mínimo é redefinido com base no que foi observado.

## W1.3 — escrita textual mínima

Só depois de W1.2 aprovado. Entrada: cópia de `A2`.

**Operações permitidas:**

```text
objeto.textual_declaration      -> IScriptTextDocument   (leitura da propriedade)
documento.replace(texto)                                  (a UNICA escrita)
objeto.textual_implementation   -> IScriptTextDocument
documento.replace(texto)
```

`replace(new_text)` substitui o documento inteiro. É deliberadamente a operação
mais simples de verificar: o estado final não depende de offset nenhum, ao
contrário de `insert`/`remove` por linha e coluna.

A propriedade **não tem setter** (`get=True, set=False`) — escreve-se pelo
documento devolvido, nunca atribuindo à propriedade.

### Conteúdo mínimo proposto

Sujeito à forma canônica observada em W1.1/W1.2:

```iecst
VAR_GLOBAL
    g_xTesteCriacao : BOOL;
END_VAR
```

```iecst
VAR
    xLocal : BOOL;
END_VAR
```

```iecst
xLocal := FALSE;
```

A implementação **não** referencia `g_xTesteCriacao` de propósito: uma
referência cruzada entre GVL e POU acrescenta resolução de símbolo à prova, e
esta fase testa escrita textual, não resolução. A referência cruzada é assunto
de W4.

### Normalização, fixada agora

A comparação de "o que escrevi" contra "o que voltou" usa estas regras, e só
estas:

```text
fim de linha CRLF e LF sao equivalentes
espaco em branco no fim de cada linha e ignorado
presenca ou ausencia de UMA quebra de linha final e ignorada
qualquer outra diferenca e DIVERGENCIA
```

As regras estão escritas **antes** de qualquer execução, de propósito.
Acrescentar normalização depois de ver um diff indesejado é ajustar o
instrumento ao resultado.

## W1.4 — persistência, reabertura e build

Só depois das três capacidades aprovadas. Entrada: cópia **do projeto-base**.

```text
 1. aplicar o plano sobre copia descartavel nova
 2. criar GVL
 3. criar PROGRAM ST
 4. inserir os textos minimos
 5. salvar EXCLUSIVAMENTE por save_as -> A4
 6. fechar sem novo salvamento
 7. reabrir A4
 8. executar o scanner read-only (probes/21)
 9. exportar os objetos criados
10. comparar declaracao e implementacao com a normalizacao definida
11. executar build() offline
12. coletar mensagens de compilacao
13. hash do projeto-base e do resultado
14. gerar diff estrutural
15. descartar o resultado apos a validacao
```

O passo 15 não é desperdício: W1 prova **capacidade**, não produz entregável. O
artefato fica no registro da execução, fora do repositório, e o projeto
resultante é descartado.

### Risco específico do `build()`

Compilar pode disparar resolução de biblioteca. Se aparecer qualquer diálogo de
biblioteca ausente, ou qualquer indício de tentativa de download, **aborta** —
`download_missing_libraries` é proibido pelo contrato, e uma resolução
automática seria a mesma coisa por outro caminho.

Mensagem de compilação é coletada com `Severity`, `Text`, `Position` e
`ObjectGuid` (disponíveis no `ScriptMessage` do MasterTool X, `docs/27` §6).
**Aviso não é erro**, e o critério de sucesso é "sem erro", com os avisos
registrados na íntegra.

## Allowlist

Literal, fechada, por tipo declarante e nome de membro:

| API | Fase |
|---|---|
| `IScriptIecLanguageObjectContainer.create_gvl` | W1.1, W1.4 |
| `IScriptIecLanguageObjectContainer4.create_program` | W1.2, W1.4 |
| `IScriptIecLanguageObjectContainer.create_pou` — **apenas** se a interface real exigir a sobrecarga tipada, e apenas com `PouType.Program` + GUID ST | W1.2, W1.4 |
| `IScriptTextDocument.replace` | W1.3, W1.4 |
| `IScriptProject.save_as` | todas |
| `IScriptApplication.build` | W1.4 |

Leituras auxiliares já aprovadas continuam permitidas para navegação,
identidade, enumeração, exportação, leitura textual e verificação —
`get_children`, `get_name`, `textual_declaration`, `textual_implementation`,
`IScriptImplementationLanguages.st`, `export_xml`, `path`, `dirty`.

**Qualquer API fora desta lista é proibida**, inclusive se existir, funcionar e
parecer óbvia.

## Blocklist explícita

```text
save() sobre o projeto de entrada     criacao ou alteracao de device
alteracao do Device Repository        criacao ou alteracao de task
Program Call                          bibliotecas
compiler version                      login / online / download / force
boot project                          SuppressPrompts
download automatico de biblioteca     importacao generica (import_xml, import_native)
remocao                               rename
clone                                 alteracao de GUID
tratamento automatico de conflito     acesso dinamico por nome de metodo
getattr para selecionar operacao mutavel
reflexao para invocar mutador
```

As três últimas linhas são a regra que sustenta as demais: **o nome do método
mutável vem escrito no código**. Um `getattr(obj, nome_calculado)` torna a
allowlist decorativa, porque o que será chamado deixa de ser legível no
próprio arquivo.

## Plano de alteração — schema preliminar

Validado **antes** de abrir o MasterTool. Plano inválido = nada é lançado.

```json
{
  "schema_version": "1.0",
  "operation_id": "w1-1-create-gvl",
  "phase": "W1.1",
  "input_project": {
    "path": "<...>\\base\\W1-base.project",
    "sha256": "<...>"
  },
  "working_copy": {
    "path": "<...>\\run-<id>\\W1-work.project",
    "sha256_expected": "<igual ao de entrada>"
  },
  "output_project": {
    "path": "<...>\\run-<id>\\A1.project",
    "must_not_exist": true
  },
  "mastertool": {
    "product": "MasterTool X",
    "version": "4.1.0.11",
    "script_engine": "4.2.0.0",
    "install_root": "C:\\Program Files\\Altus\\MT9000 4.1.0"
  },
  "container": {
    "node_path": "root/1/1/0",
    "resolved_by": "probes/21 scan",
    "must_be_unique": true
  },
  "allowlist": [
    "IScriptIecLanguageObjectContainer.create_gvl",
    "IScriptProject.save_as"
  ],
  "operations": [
    { "kind": "create_gvl", "name": "GVL_AI_TESTE" }
  ],
  "expected_diff": {
    "objects_added": 1,
    "objects_removed": 0,
    "objects_modified": 0,
    "kinds_added": ["gvl"]
  },
  "success_criteria": [
    "exatamente uma GVL nova, de nome GVL_AI_TESTE",
    "A1 existe e reabre",
    "projeto-base com sha256 inalterado"
  ],
  "abort_criteria": [
    "nome ja existente",
    "container ambiguo",
    "qualquer dialogo",
    "saida ja existente"
  ]
}
```

Campos obrigatórios em qualquer fase: hash do projeto de entrada, instalação
exata, operações **em ordem**, nomes dos objetos, linguagem (quando aplicável),
hash dos textos (em W1.3/W1.4), arquivo de saída, limites esperados do diff,
critérios de sucesso e critérios de aborto.

## Precondições

Verificadas **antes** de abrir o MasterTool. Qualquer uma falhando, nada é
lançado:

```text
projeto-base e copia com hashes iguais       projeto offline
nenhum outro MasterTool aberto               arquivo de saida INEXISTENTE
nomes-alvo AUSENTES no projeto de entrada    container IEC unico e inequivoco
GUID ST encontrado em runtime                contrato e plano aprovados
fase controlada da etapa ativa, autorizada em COMMIT SEPARADO
READ_ONLY_PHASE = True (sempre)              UI visivel
usuario presente
```

A checagem de instância aberta usa o nome de processo derivado do executável
(`MT9000*`) — o harness versionado ainda procura `MT8500*` e daria "sem
instância" sempre.

## Pós-condições

A execução só é aprovada com **todas**:

```text
projeto-base com SHA-256 identico            arquivo salvo existe, em caminho DIFERENTE
exatamente uma GVL e um PROGRAM adicionados  nenhum objeto persistente inesperado
nomes e tipos conferem                       linguagem e ST, confirmada por GUID
declaracao e implementacao equivalentes sob a normalizacao definida
export read-only confirma o conteudo         build offline sem erro
nenhum dialogo inesperado                    nenhum processo orfao
nenhuma configuracao global alterada         .opt confinados ao diretorio descartavel
```

## Diff estrutural

Compara a **árvore persistente do projeto** reaberto, nunca a pasta:

```text
objetos IEC   nomes   tipos   linguagens
declaracoes   implementacoes   referencias   mensagens de build
```

Ignora **apenas**:

```text
objetos comprovadamente transientes (is_transient_object)
GUIDs de sessao ja documentados como instaveis (docs/22)
timestamps e metadados volateis explicitamente catalogados
arquivos .opt
```

**Nenhuma regra de exclusão nova entra depois de observar um diff
indesejado sem revisão.** Um diff que incomoda é achado até prova em
contrário; silenciá-lo na hora é como ajustar o teste ao bug.

## Critérios de aborto

Abortar **sem salvar**:

```text
nome ja existente                container ambiguo
GUID ST ausente ou ambiguo       qualquer dialogo
pedido de conversao              biblioteca ausente
alteracao de compiler version    projeto online
excecao DEPOIS da primeira mutacao   objeto extra inesperado
saida ja existente               divergencia de hash de entrada
falha no artefato de conclusao
```

Como **não existe rollback transacional**, qualquer falha depois do primeiro
`create_*` invalida a **cópia inteira**: ela é descartada, não corrigida. Essa é
a consequência direta de `create_*` devolver o objeto já inserido na árvore.

## Gate — estado e fases seguintes

A autorização de W1.1 **já ocorreu**, em `b8ad7bb`, em commit isolado contendo
apenas o gate e os seus testes estruturais:

```text
CONTROLLED_WRITE_PHASE = "W1_1_CREATE_GVL"
allowlist               = create_gvl, save_as
READ_ONLY_PHASE         = True (inalterado, e assim permanece)
```

Cada fase seguinte exige o **seu próprio commit isolado**, com o mesmo rito
(`docs/28` §14): plano aprovado, allowlist revisada nome a nome, testes
estruturais no mesmo commit, nenhuma implementação de probe junto.

```text
W1.2  acrescenta create_program (ou create_pou, conforme a interface real)
W1.3  acrescenta replace
W1.4  acrescenta build
```

`save_as` fica autorizado **somente nas fases que precisarem dele**, e nenhuma
dessas autorizações é antecipada agora. Uma allowlist que cresce por
antecipação deixa de descrever o que está em uso e passa a descrever o que se
pretende — e é justamente a diferença entre as duas que o gate existe para
manter visível.

A implementação do probe e a autorização da fase **nunca entram no mesmo
commit**. Separados, o histórico mostra a autorização como decisão datada;
juntos, ela vira uma linha perdida dentro de um slice de funcionalidade.

## Instrumentação futura — a propor, não a implementar

Nada disto existe ainda:

| Item | Papel |
|---|---|
| probe W1 específico | uma fase por execução, allowlist literal no código |
| wrapper PowerShell supervisionado | fail-closed sem `-Execute`, processo por nome derivado do exe |
| manifesto antes/depois | hashes, plano aplicado, resultado por operação |
| journal append-only | uma linha por operação, escrita **antes** de cada mutação |
| artefato de conclusão | a fonte de "terminou", já que exit code não propaga |
| códigos de saída | distinguindo "verificação falhou" de "uso inválido" |
| captura de prompts | `LogPrompts`, nunca `SuppressPrompts` |
| detecção de processo | instância prévia e órfão, por `MT9000*` |
| hash dos arquivos | entrada, saída e artefatos |
| relatório de diff | estrutural, com as exclusões declaradas |
| validação read-only após reabertura | o juiz, conforme `docs/28` §9 |

O **journal append-only** merece nota: ele é escrito *antes* de cada mutação,
não depois. Um journal escrito depois não registra a operação que travou — e é
exatamente essa que interessa.

## O que este plano não cobre

```text
projeto existente ou de producao     Ladder e qualquer linguagem grafica
DUT, enum, struct, PersistentVars    FUNCTION_BLOCK e FUNCTION
metodo e propriedade de FB           acao e transicao
task e Program Call                  biblioteca
device e hardware                    referencia cruzada entre GVL e POU
resolucao de simbolo                 import_xml (rota B)
```

Tudo isso é W4 ou posterior, e nenhum item entra em W1 por conveniência.

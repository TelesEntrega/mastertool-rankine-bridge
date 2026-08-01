# Plano W1.4 — integração completa com `build`

Plano de execução e revisão do marco **W1.4**. Documento **não normativo**:
quem manda é
[`28-contrato-escrita-controlada-mastertool-x.md`](28-contrato-escrita-controlada-mastertool-x.md).
Onde este plano e o contrato divergirem, o contrato prevalece e o plano está
errado.

> **Este documento é o PLANO, e já foi cumprido.** Ele foi escrito antes de
> qualquer execução, e o que ele previu aconteceu na `run-019` —
> [`docs/37`](37-execucao-w1-4-autoria-integrada.md) é o registro. Onde os dois
> divergem, **o registro de execução manda**: ele mede, este planeja.
>
> Duas coisas que este plano declarava como lacuna e que a execução **fechou**:
> a fonte das mensagens de compilação (estava na docstring do próprio `build()`,
> `ScriptApplication.pyi` L41-49) e a impossibilidade de afirmar "sem erro" sem
> lê-las.

**Este documento não abriu gate nenhum e não abriu nenhuma fase.** Quando foi
escrito, `CONTROLLED_WRITE_PHASE` era `None`, e autorizar a fase foi ato à
parte, em commit isolado, com o rito de `docs/28` §14. A fase foi aberta,
executada e **encerrada**; o ponteiro voltou a `None`.

## 1. Estado de referência

| | |
|---|---|
| W0 · W1.1 · W1.2 · W1.3 | encerrados e aprovados (ver `docs/18`) |
| Gate | `READ_ONLY_PHASE = True` · `CONTROLLED_WRITE_PHASE = None` |
| Projeto-base de W1.4 | `TemplateExemplo v1.project`, **503.040 bytes**, SHA-256 `596625796e4efd54d3cc2d6286e858b683f0f58de66ab9a36eed532dd1d815f5`, com cartões de I/O configurados |
| Baseline estrutural anterior | **INVALIDADA** — era medida sobre a base sem cartões de I/O (3 raízes, 34 nós, `structure_sha256 b2825550…`, `node_path root/1/0/0`, `type_guid` do `Application` `639b491f-5557-464c-af91-1471bac9f549`) |
| Baseline estrutural nova | **ainda não medida** — precisa de varredura read-only com `probes/21` sobre cópia descartável da base nova, **antes** de qualquer sessão de W1.4 |
| GUID da linguagem ST | `cc393387-a21c-4f68-a3e3-84c36951965d` (medido, `docs/30`) |
| `type_guid` de GVL | `ffbfa93a-b94d-45fc-a329-229860183b1d` (medido, `docs/29`) |
| `type_guid` de POU | `6f9dac99-8de1-4efc-8465-68ac443b7d08` — identifica POU, **não** distingue `PROGRAM` de `FUNCTION_BLOCK` (lacuna declarada em `docs/30`) |

Este documento não abre nenhuma fase controlada. Escrever o plano é o passo 1
do rito de `docs/28` §14; os passos seguintes — allowlist revisada, decisão
humana, commit isolado com testes estruturais — são atos futuros e distintos.

## 2. Por que W1.4 volta ao projeto-base

W1.1, W1.2 e W1.3 isolaram cada capacidade deliberadamente: criar GVL, criar
`PROGRAM`, e escrever texto foram provadas **uma de cada vez**, cada uma sobre
a saída congelada da anterior ou sobre o projeto-base, nunca misturadas na
mesma sessão (`docs/29` §"Por que W1 é subdividido"). Essa subdivisão existe
para que uma falha aponte para uma única capacidade.

W1.4 inverte esse cuidado de propósito: agora que as quatro capacidades —
`create_gvl`, `create_program`, `replace`, `save_as` — estão provadas
separadamente, a variável sob teste deixa de ser "a API individual funciona" e
passa a ser "**a composição das quatro, em sequência, sobre um projeto real,
produz um artefato que compila**". Reaproveitar `A1`, `A2` ou `A3` faria a
prova de integração depender de um artefato intermediário já manipulado por
script — e W1.4 existe justamente para provar que a cadeia funciona **do
zero**, a partir do estado que um projeto de produção realmente tem.

Por isso W1.4 recomeça do **projeto-base**, não da saída de W1.3. Isso é
coerente com `docs/29` §"Encadeamento das entradas": W1.1→W1.2→W1.3 encadeiam
saídas verificadas; W1.4, por ser a prova de integração, não herda nenhuma.

### O que a troca de base implica

A base mudou em 2026-07-31, **depois** de W1.1 e W1.2 terem rodado sobre a
base anterior. Isso não invalida W1.1 e W1.2 — eles provaram **capacidade**,
não propriedade de um arquivo específico (`docs/29` §"Base nova"). Mas invalida
qualquer número estrutural que W1.4 precise da base para funcionar:

```text
contagem de raizes                 (era 3, na base anterior)
contagem de nos                    (era 34, na base anterior)
hash deterministico da estrutura   (era b2825550..., na base anterior)
node_path do Application           (era root/1/0/0, o mais critico)
type_guid do Application           (era 639b491f-..., na base anterior)
```

`node_path` é caminho de **índices**, não identidade. Cartões de I/O
acrescentam nós sob o `Device`, e um índice deslocado faz `root/1/0/0` deixar
de apontar para o `Application` — o preflight abortaria com
`container_not_found`, comportamento correto por motivo evitável.

**Nenhum desses números é reaproveitável da base anterior.** Antes de
qualquer execução de W1.4, é obrigatória uma varredura read-only nova com
`probes/21`, sobre uma cópia descartável da base nova, e o recongelamento dos
números acima como baseline estrutural de W1.4. Onde este documento cita um
`node_path` ou uma contagem, é placeholder a preencher por essa medição — não
um valor a inventar.

## 3. A cadeia de operações

Em ordem, sobre cópia descartável nova do projeto-base:

```text
 1. create_gvl        -> cria GVL_AI_TESTE, vazia
 2. create_program    -> cria PRG_AI_TESTE, linguagem ST por GUID
 3. replace (decl GVL)  -> grava a declaracao da GVL
 4. replace (decl PRG)  -> grava a declaracao do PROGRAM
 5. replace (impl PRG)  -> grava a implementacao do PROGRAM
 6. save_as           -> A4, arquivo NOVO
 7. fechar sem novo salvamento
 8. reabrir A4, sessao independente
 9. build()           -> compilacao offline
10. verificacao read-only (probes/21, export textual, indice ST)
11. diff estrutural   -> comparar com a baseline nova
```

### Justificativa de cada operação, e por que essa ordem

- **`create_gvl` antes de `create_program`**: a implementação do PROGRAM
  referencia `GVL_AI_TESTE.g_xTesteCriacao`; a GVL precisa existir antes de
  qualquer texto que a cite ser escrito, senão o `replace` da implementação
  estaria referenciando um símbolo inexistente — achado que não teria nada a
  ver com a capacidade de escrever.
- **`replace` da declaração da GVL antes da declaração do PROGRAM**: não há
  dependência real entre as duas declarações, mas manter a ordem de criação
  (GVL primeiro) evita ambiguidade no journal sobre qual objeto uma falha
  intermediária atingiu.
- **`replace` da implementação do PROGRAM por último, entre os `replace`**:
  ela é a única que **lê** outro objeto (a GVL, via `GVL_AI_TESTE.`), então só
  faz sentido escrevê-la depois que a declaração da GVL já está persistida na
  árvore em memória.
- **`save_as` só depois dos cinco passos de escrita**: é a mesma regra de
  `docs/28` §8 — nenhum `save()` sobre a entrada, e a única persistência é por
  arquivo novo, depois que toda a sequência de mutação terminou.
- **fechar e reabrir antes de qualquer verificação**: é o que distingue "o
  objeto e o texto existiram na sessão" de "foram persistidos" (`docs/28` §8,
  já usado em W1.1, W1.2 e W1.3).
- **`build()` só depois da reabertura**: compilar sobre a sessão que acabou de
  escrever provaria, no máximo, que o texto em memória compila — não que o
  texto **persistido** compila. A reabertura remove essa ambiguidade.
- **verificação read-only e diff depois do `build`, nunca antes**: o build
  pode alterar estado interno de compilação (mensagens, cache) que a
  verificação read-only quer capturar; rodar a verificação antes descreveria
  um estado que a sessão ainda vai mudar.

### Allowlist da fase `W1_4_INTEGRATED_BUILD`

```text
create_gvl        create_program        replace        save_as        build
```

Cinco nomes, literais, e nenhum além.

> **Correção de nome, feita depois da execução.** Este documento chamou a fase
> de `W1_4_INTEGRATED_AUTHORING` enquanto ela era hipótese. Os instrumentos
> fixaram `W1_4_INTEGRATED_BUILD`, e foi esse o nome aberto e fechado no gate.
> Dois nomes para a mesma fase seriam duas portas, e a segunda envelheceria em
> silêncio — por isso há teste exigindo que `W1_4_INTEGRATED_AUTHORING` **não**
> exista no mapa de allowlists.
>
> A fase foi executada e encerrada. Registro em
> [`docs/37`](37-execucao-w1-4-autoria-integrada.md).

## 4. `build()` entra aqui e só aqui

`build()` nunca esteve na allowlist de W1.1, W1.2 ou W1.3, e `docs/29` já
registrava por quê, ao encerrar W1.3: **compilar ali teria misturado "o texto
persistiu" com "o texto compila"**.

A razão para separar as duas provas é estrutural, não estética. `replace`
grava um texto num documento e a verificação de W1.3 comparava esse texto,
depois de reaberto, byte a byte (sob a normalização de `docs/29`) com o texto
planejado — uma prova puramente sintática, sem qualquer noção de que aquele
texto faz sentido como programa. `build()` é outra prova inteiramente: ela
invoca o compilador do MasterTool e pergunta se o texto persistido, dentro da
árvore inteira do projeto, resolve símbolos, tipos e referências.

Se W1.3 tivesse chamado `build()`, um erro de compilação — por exemplo, uma
referência não qualificada que o pragma `qualified_only` rejeita — teria
aparecido misturado com a prova de que `replace` grava e persiste
corretamente. Não haveria como saber, só pelo resultado, se `replace` falhou
em persistir ou se o texto persistido corretamente é que estava errado. São
achados de naturezas diferentes: um é sobre a **capacidade de escrever**, o
outro é sobre o **conteúdo escrito**. W1.4 é o primeiro marco em que faz
sentido misturá-los, porque é o primeiro que testa a cadeia inteira e não uma
API isolada.

### O prefixo obrigatório e o que ele revela

A implementação de `PRG_AI_TESTE` é:

```iecst
xLocal := GVL_AI_TESTE.g_xTesteCriacao;
```

O prefixo `GVL_AI_TESTE.` é **obrigatório**, não estilo. A GVL carrega
`{attribute 'qualified_only'}`, que exige que toda referência externa à GVL
seja qualificada pelo nome dela. Escrever apenas `g_xTesteCriacao := ...`
sem o prefixo faria o `build()` falhar por símbolo não resolvido — e esse
seria exatamente o tipo de achado que este documento pede para não confundir
com falha de capacidade: seria um achado sobre o **conteúdo** (a referência
precisa do prefixo por causa do pragma), não sobre a **capacidade de
escrever** (o `replace` teria gravado e persistido o texto perfeitamente).
É por isso que o texto final de W1.4 já inclui o prefixo desde o plano — a
lacuna que este documento evita é justamente a de propor um texto que falharia
no build por um motivo já conhecido.

### O GUID da linguagem não viaja como texto

Herdado de W1.2 e **obrigatório aqui**, porque W1.4 chama `create_program`:

```text
create_program recusa str com
    TypeError: expected Nullable[Guid], got str
```

O plano só transporta texto — JSON não tem tipo `Guid` — e o IronPython não
converte sozinho. A conversão via `System.Guid` acontece na fase de
**precondição**, nunca entre a guarda e a chamada, e falha de conversão é
`precondition_failed`, não `create_program_failed`: uma nem chegou a pedir
autorização, a outra sim.

Foi assim que a `run-005` reprovou, **antes de tocar o projeto**. Repetir o
erro em W1.4 custaria uma sessão inteira, porque aqui a falha ocorreria no meio
de uma cadeia de cinco mutações — e a cadeia inteira seria descartada.

## 5. Riscos específicos do `build`

`build()` é a primeira operação de W1 que pode acionar comportamento fora do
controle direto do script: resolução de bibliotecas referenciadas pelo
projeto.

```text
build pode disparar resolucao de biblioteca
qualquer dialogo de biblioteca ausente        -> ABORTA
qualquer indicio de tentativa de download     -> ABORTA
download_missing_libraries                    -> PROIBIDO, sem excecao
set_compilerversion_to_newest                 -> PROIBIDO, sem excecao
```

`download_missing_libraries` está na lista de proibições permanentes de
`docs/28` §3 porque **faz rede** — medido, não presumido. Uma resolução
automática de biblioteca ausente durante o `build`, mesmo sem chamar esse
método explicitamente, seria o mesmo efeito por outro caminho: rede acionada
por uma operação que o operador não autorizou explicitamente naquele
instante. Por isso o critério de aborto não é "não chamar
`download_missing_libraries`" — é "qualquer indício de download aborta",
incluindo diálogo de biblioteca ausente que o próprio `build` dispare.

`set_compilerversion_to_newest` continua proibido pela mesma razão registrada
em `docs/28` §3: muda a versão de compilador do **projeto**, mutação de alto
impacto disfarçada de configuração. Nada em W1.4 precisa dela — a versão de
compilador do projeto-base é a que existe na cópia, e nunca é alterada.

### Coleta de mensagens

Cada mensagem de compilação é coletada com:

```text
Severity      Text      Position      ObjectGuid
```

Campos disponíveis no `ScriptMessage` do MasterTool X (`docs/27` §6, citado em
`docs/29`). **Aviso não é erro.** O critério de sucesso do `build` é "sem
erro" (`Severity` de erro ausente na coleta), com todos os avisos —
independente de quantos — registrados na íntegra no artefato da sessão.
Descartar avisos ou resumi-los apagaria a única evidência de que a sessão os
viu e decidiu que não bloqueavam.

## 6. Diff permitido

Exatamente:

```text
+ GVL_AI_TESTE                    (objeto persistente novo)
+ PRG_AI_TESTE                    (objeto persistente novo)
~ textual_declaration de GVL_AI_TESTE     (o texto planejado da secao 0)
~ textual_declaration de PRG_AI_TESTE     (o texto planejado da secao 0)
~ textual_implementation de PRG_AI_TESTE  (o texto planejado da secao 0)
```

Nada além disso. Qualquer outro objeto criado, removido, renomeado ou com
texto alterado reprova a sessão inteira — inclusive POUs e GVLs padrão do
esqueleto do projeto-base e inclusive os cartões de I/O que a base nova
carrega. A regra de `docs/29` §"O diff estrutural" continua valendo: `.opt`,
timestamps catalogados, GUIDs de sessão instáveis (`docs/22`) e objetos
transientes de verdade (`is_transient_object`) são separados, nunca tratados
como alteração persistente.

## 7. Verificação read-only pós-build

As consultas do lado somente-leitura (varredura da árvore, export textual,
índice ST) devem, sobre `A4` reaberto depois do `build`, encontrar:

```text
a declaracao da variavel global      g_xTesteCriacao : BOOL, em GVL_AI_TESTE
a leitura dela                       GVL_AI_TESTE.g_xTesteCriacao, na implementacao de PRG_AI_TESTE
a escrita em xLocal                  xLocal := ..., na implementacao de PRG_AI_TESTE
```

Essas três presenças são o que fecha o ciclo: não basta o `build` reportar
"sem erro" — o índice ST, que já está validado como camada independente
(`docs/18`, cadeia completa ST), precisa **encontrar** a declaração e as duas
referências no texto persistido. Um `build` sem erro e um índice que não
encontra a variável seriam contraditórios, e essa contradição é achado, não
detalhe a ignorar.

## 8. Fault injection obrigatório

Cada item da lista abaixo precisa ter, no artefato da sessão, o estado
observado e a consequência sobre a cópia de trabalho. **Nenhum item desta
lista pode gerar aprovação parcial automática** — a razão é a mesma que já
rege W1.1 a W1.3 (`docs/28` §10, `docs/29` §"Critérios de aborto"): não existe
rollback transacional na API do MasterTool X, `create_*` devolve o objeto já
inserido na árvore sem passo de confirmação, e qualquer falha depois do
primeiro `create_*` invalida a **cópia inteira**, nunca uma operação isolada
dela. Uma "aprovação parcial" implicaria que algum subconjunto da cadeia foi
aceito sem que a cadeia inteira tivesse sido verificada — e é exatamente essa
aceitação implícita que o rito de W1 inteiro existe para impedir.

| Ponto de injeção | Estado esperado | Consequência sobre a cópia |
|---|---|---|
| falha antes de qualquer mutação (precondição) | `precondition_failed`, nenhuma API mutável chamada | cópia nunca é usada; descartada ou nem criada |
| falha após `create_gvl` | GVL já inserida na árvore em memória, nada persistido | cópia descartada inteira, sem tentar `remove` |
| falha após `create_program` | GVL e PROGRAM inseridos em memória | cópia descartada inteira |
| falha após o 1º `replace` (decl GVL) | texto da GVL alterado em memória | cópia descartada inteira |
| falha após o 2º `replace` (decl PRG) | texto da declaração do PROGRAM alterado em memória | cópia descartada inteira |
| falha após o 3º `replace` (impl PRG) | texto da implementação alterado em memória | cópia descartada inteira |
| falha em `save_as` | nenhum arquivo novo criado, ou arquivo parcial | cópia de trabalho e qualquer saída parcial descartadas |
| output criado mas reabertura falha | arquivo existe, mas a sessão independente não consegue abri-lo ou lê-lo | saída tratada como inválida; não promovida; investigada como achado, nunca reaberta à força |
| build com erro | `Severity` de erro presente na coleta de mensagens | sessão reprovada; avisos (se houver) registrados na íntegra; saída não promovida |
| diff inesperado | qualquer objeto ou texto fora da lista da seção 6 | sessão reprovada integralmente, mesmo que o restante do diff esteja correto |
| completion ausente | artefato de conclusão não gravado ou ilegível | sessão tratada como **falha de artefato**, distinta de falha de verificação — critério de aborto próprio (`docs/28` §11) |
| launcher retorna zero sem artefato | exit code 0, mas nenhum artefato de conclusão | **não é sucesso** — a propagação de exit code nunca foi observada (`docs/28` §7); só o artefato conta |
| processo não fecha | MasterTool permanece aberto além do esperado | script **nunca mata processo**; timeout é só proteção, não gatilho de `Stop-Process` |
| diálogo inesperado | qualquer diálogo fora do fluxo previsto | cancelado e **registrado com o texto exato**; sessão abortada |

Cada linha desta tabela precisa, quando o slice de implementação existir, de
um teste ou de uma execução real que a exercite — este documento apenas define
o vocabulário fechado e a consequência esperada; não implementa nenhum teste.

## 9. Estados fechados da sessão

Vocabulário fechado, análogo ao de W1.1/W1.2 (`docs/30` §"Estados do
preflight"), mas cobrindo a cadeia inteira. **Somente um estado representa
produto utilizável** — o que reaproveita `A4`:

```text
precondition_failed              -> falha antes de qualquer mutacao
create_gvl_failed                -> falha na 1a mutacao
create_program_failed            -> falha na 2a mutacao
replace_gvl_declaration_failed   -> falha no 1o replace
replace_program_declaration_failed -> falha no 2o replace
replace_program_implementation_failed -> falha no 3o replace
save_as_failed                   -> falha na persistencia
reopen_failed                    -> arquivo criado, reabertura falhou
build_failed                     -> build reportou erro
diff_unexpected                  -> diff fora da secao 6
completion_missing               -> artefato de conclusao ausente ou ilegivel
dialog_unexpected                -> dialogo fora do previsto
orphan_process                   -> processo nao fechou
fatal                            -> excecao nao categorizada

integration_verified             -> UNICO estado de produto utilizavel:
                                     build sem erro, diff exatamente da secao 6,
                                     verificacao read-only da secao 7 confirmada,
                                     nenhum dialogo, nenhum orfao, artefato presente
```

Nenhum outro estado autoriza promoção da cópia. `integration_verified` exige
**todas** as condições ao mesmo tempo, não uma combinação parcial delas —
consistente com a regra da seção 8 de que nenhuma falha gera aprovação
parcial automática.

## 10. Critérios de aborto

### Antes da primeira mutação

```text
hash da base divergente             instalacao do MasterTool diferente da esperada
outra instancia do MasterTool aberta   arquivo de saida ja existente
container IEC ausente ou ambiguo    GUID ST ausente ou ambiguo
nomes-alvo ja existentes no projeto de entrada
fase controlada incorreta ou ausente   plano de alteracao ausente ou invalido
baseline estrutural nova NAO medida (probes/21 nao rodou sobre a base nova)
```

O último item é específico de W1.4: sem a baseline estrutural recongelada
(seção 2), não há como o preflight confirmar `node_path` e `type_guid` do
container — abrir a sessão sem isso repetiria o erro já descrito ("presumir
continuidade seria o erro que este projeto não comete").

### Depois da primeira mutação

```text
qualquer excecao em qualquer passo da cadeia    diff fora da secao 6
qualquer dialogo                                 pedido de conversao ou atualizacao
biblioteca ausente ou indicio de download        alteracao de compiler version
projeto ficando online                           processo orfao apos encerrar
```

Como não existe rollback transacional, qualquer aborto depois de `create_gvl`
descarta a **cópia inteira** — nunca uma tentativa de desfazer passo a passo.
É a mesma regra de `docs/28` §10 e `docs/29`/`docs/31`, sem exceção nova para
W1.4.

## 11. O que W1.4 não cobre

```text
FUNCTION_BLOCK e FUNCTION           DUT, enum, struct, PersistentVars
task e Program Call                 biblioteca nova (as ja referenciadas no
                                     projeto-base sao as unicas em jogo)
hardware e device                   Ladder e qualquer linguagem grafica
projeto existente ou de producao    resolucao de simbolo alem do minimo
                                     necessario para o build de W1.4
```

Tudo isso permanece W4 ou posterior (`docs/18` §"Marcos"), e nenhum item entra
em W1.4 por conveniência.

## Lacunas declaradas neste documento

Registradas aqui, em vez de decididas por suposição:

```text
baseline estrutural da base nova (raizes, nos, node_path do Application,
  type_guid do Application, hash deterministico) ainda NAO medida;
  instrumento: probes/21, sobre copia descartavel, antes de qualquer sessao
type_guid de POU nao distingue PROGRAM de FUNCTION_BLOCK (lacuna ja
  declarada em docs/30, herdada aqui sem re-derivacao)
```

Nenhum outro número deste documento foi inventado ou re-derivado: os valores
de GUID, `type_guid`, hash e tamanho da base nova vêm citados tal como
recebidos, e onde a medição necessária ainda não existe, este documento diz
isso explicitamente em vez de propor um valor.

# Contrato da escrita controlada no MasterTool X

Documento **normativo** da trilha `MasterTool X controlled project authoring`.
Define o que pode ser escrito, sob que condições, e o que aborta.

Onde este contrato divergir de qualquer outro documento, ele prevalece para
operações de escrita. A evidência que o sustenta está em
[`27-reconhecimento-mastertool-x.md`](27-reconhecimento-mastertool-x.md) — este
documento **não** repete medição; ele decide regra.

## Estado deste contrato

O marco W0 está concluído e comprovado. **Este documento não autoriza operação
nenhuma**: autorização é ato à parte, em commit isolado, e nunca efeito
colateral de um slice de implementação.

A fase `W1_1_CREATE_GVL` está autorizada desde `b8ad7bb`, com duas operações e
nada mais.

```text
READ_ONLY_PHASE        = True                  <- permanece True SEMPRE
CONTROLLED_WRITE_PHASE = "W1_1_CREATE_GVL"     <- excecao nomeada, autorizada
operacoes autorizadas  = create_gvl, save_as
```

### Autorização controlada dentro de uma fase globalmente read-only

Ler isto como "o modo read-only foi desligado" é ler errado. **`READ_ONLY_PHASE`
permanece `True` e continua proibindo as operações legadas de escrita geral**;
o que existe é uma **exceção nomeada e mínima** dentro dessa fase.

A distinção não é retórica. Um booleano global de escrita autoriza tudo de uma
vez; uma fase nomeada autoriza uma lista literal, e sair dela exige outro
commit. Só o segundo modelo permite dizer, em qualquer momento do histórico,
exatamente quais operações estavam liberadas.

## 0. O modelo do gate

Sete regras, e nenhuma delas é opcional:

```text
1. READ_ONLY_PHASE permanece True; ele NUNCA e trocado para False
2. toda operacao mutavel conhecida pertence ao registro literal
   MASTERTOOL_MUTATING_OPERATIONS
3. toda operacao mutavel passa por UMA UNICA porta de autorizacao
4. uma fase controlada NOMEADA pode autorizar uma allowlist literal minima
5. W1.1 autoriza somente create_gvl e save_as
6. operacao desconhecida, fase desconhecida ou configuracao incompleta
   falha FECHADA
7. nao existe autorizacao por prefixo, padrao, curinga ou correspondencia
   parcial
```

> **A existência de uma API mutável que ainda não esteja catalogada não a torna
> neutra; torna-a proibida.**

Esse princípio é o que dá sentido à regra 6. Sem ele, "não previmos essa
operação" viraria "essa operação está liberada" — que foi exatamente o defeito
corrigido em `b8ad7bb`, descrito na seção seguinte.

## 0.1 O defeito de cobertura do gate anterior

Encontrado em 2026-07-31, **por teste, sem nenhuma invocação de API do
MasterTool e sem nenhuma mutação executada**.

A guarda antiga conhecia apenas sete nomes legados (`save_project`,
`import_object`, `create_object`, `delete_object`, `modify_object`,
`set_declaration`, `set_implementation`) e devolvia permissão para **qualquer
outro nome**. Os nomes reais das APIs do MasterTool X nunca tinham sido
registrados. O resultado, medido com `READ_ONLY_PHASE = True`:

```text
create_gvl -> permitido    save_as    -> permitido    create_program -> permitido
replace    -> permitido    build      -> permitido    import_xml     -> permitido
```

Ou seja: as operações legadas eram bloqueadas, e a superfície inteira do
MasterTool X passava. O gate protegia o vocabulário antigo e ignorava o novo —
a falha não era de política, era de **cobertura**.

A correção, em `b8ad7bb`:

```text
registro LITERAL de 40 operacoes mutaveis catalogadas (docs/27 §7)
fail-closed para nome desconhecido, parcial, com curinga ou fora de tipo
autorizacao por FASE NOMEADA, com allowlist literal por fase
UMA politica de decisao: a guarda legada desvia toda operacao mutavel
  do MasterTool X para a porta unica, inclusive as autorizadas
testes estruturais cobrindo nomes exatos e entradas adversariais
```

## 1. Escopo

Aplica-se a toda operação que crie, altere, renomeie, remova, importe, salve
ou compile objeto de projeto no MasterTool X (`MT9000.exe`), por script ou por
ferramenta deste repositório.

Não se aplica a leitura, navegação, exportação e inventário — esses seguem os
contratos já existentes (`docs/16`, `docs/19`, `docs/22`, `docs/23`).

## 2. Projeto descartável obrigatório

Nenhuma escrita ocorre em projeto industrial. Nem em W1, nem em W2, nem em W3.

```text
1. o projeto-base NUNCA e aberto
2. copia-se o .project para diretorio PROPRIO, fora do repositorio, SEM espaco
3. calcula-se SHA-256 da base e da copia; devem ser iguais
4. a copia e artefato EXCLUSIVO de uma sessao: reaproveitar copia de sessao
   anterior e recusado
5. so a copia e aberta
```

O diretório é próprio, e não compartilhado com o arquivo de origem, porque
abrir um projeto **cria arquivos irmãos** — `<nome>-AllUsers.opt` e
`<nome>-<usuario>-<maquina>.opt` (medido, `docs/27` §9). Numa pasta de
produção, esses arquivos seriam escritos ao lado do projeto real.

**Escrita em projeto industrial só é considerada depois de W3 concluído**, e
por decisão humana registrada — não por este contrato.

## 3. Proibições permanentes

Valem em **todos** os marcos, W1 a W5, e não são relaxáveis por plano de
alteração:

```text
nenhuma sessao online          nenhum login em CLP
nenhum download                nenhum force de variavel
nenhuma alteracao de hardware  nenhuma alteracao no repositorio de dispositivos
nenhum --noUI                  nenhuma execucao sem operador presente
```

### APIs proibidas por nome

Cada uma com o motivo medido, não presumido:

| API | Por que |
|---|---|
| `ScriptPromptHandling.SuppressPrompts` | suprimir diálogo converte parada segura em decisão silenciosa. A regra do projeto é "diálogo inesperado → cancelar e registrar"; suprimir a torna inexequível. `LogPrompts` é o único valor aceitável |
| `IScriptLibManObject3.download_missing_libraries` | faz rede |
| `IScriptProjectSettings2.set_compilerversion_to_newest` | muda a versão de compilador do projeto — mutação de alto impacto com aparência de configuração |
| `IScriptGateway.perform_network_scan` | varredura ativa de rede |
| `IScriptDeviceObject.unplug` / `update` / `set_gateway_and_ip_address` | alteram hardware configurado |
| `IScriptDeviceRepository.import_device` / `remove_device` / `import_vendor_description` | alteram o repositório de dispositivos, que é **por versão instalada** (`docs/26`) e afeta todo projeto da máquina |
| `device_repository` (qualquer leitura de propriedade) | marcado em `common/compatibility.py` como capaz de iniciar comunicação |

## 4. Allowlist

Só é invocável o que estiver **catalogado em `docs/27` §7 e listado no plano de
alteração da sessão**. A allowlist é literal, por nome de membro e tipo
declarante. Não existe allowlist por padrão, por prefixo ou por categoria.

**API não catalogada é proibida** — inclusive se existir, funcionar e parecer
óbvia. O catálogo é a fronteira; alargá-lo é um slice documental próprio, com
evidência estática antes do uso.

Nunca `getattr` com nome computado. Nunca `dir()` sobre proxy CLR para
descobrir o que chamar. O nome vem escrito no código.

## 5. Plano de alteração

Toda sessão de escrita começa por um plano em JSON, escrito **antes** e
versionado como artefato da sessão:

```text
projeto-base e seu SHA-256        copia de trabalho e seu SHA-256
lista ORDENADA de operacoes       cada uma com API, argumentos e efeito esperado
allowlist literal da sessao       precondicoes verificaveis antes de cada passo
estado final esperado             criterio de sucesso por operacao
```

Operação fora do plano **aborta a sessão**. O plano não é roteiro flexível: é
declaração do que vai acontecer, contra a qual o resultado é conferido.

## 6. Precondições, verificadas antes de abrir o MasterTool

```text
executavel e a instalacao esperada, conferida por FileVersion
  (ha 4.0.0 e 4.1.0 nesta maquina; confundi-las invalida a evidencia)
nenhuma instancia do MasterTool aberta
fase controlada ativa e coerente com o marco autorizado
READ_ONLY_PHASE = True (sempre; nunca faz parte da autorizacao)
copia descartavel existe, e nova, e identica a base
diretorio de saida fora do repositorio e sem espaco
plano de alteracao presente e valido
```

Qualquer uma falhando, nada é lançado.

## 7. Execução

```text
UI VISIVEL, operador presente e olhando        offline
uma operacao por vez, na ordem do plano        sem confirmacao automatica
timeout apenas como protecao                   o script NUNCA mata processo
conclusao detectada pelo ARTEFATO              nunca pelo exit code
encerramento sem salvar, salvo o save_as previsto no plano
```

A conclusão vem do artefato porque **a propagação do exit code do script nunca
foi observada** — nem no MT8500, nem no MasterTool X (`docs/27` §9). Os `exit 0`
medidos são do processo após fechamento manual, e não dizem nada sobre o
script.

Caminho com espaço é proibido em qualquer argumento: o `--scriptargs` quebra o
valor em espaço em branco, medido no MasterTool X.

## 8. Persistência

```text
save_as OBRIGATORIO para arquivo NOVO     save() no lugar do save_as: proibido
o arquivo de entrada nunca e sobrescrito  fechar e reabrir antes de verificar
```

Salvar por cima elimina a única cópia do estado anterior. Reabrir é o que
distingue "o objeto foi criado na sessão" de "o objeto foi persistido".

## 9. Verificação — o analisador read-only é o juiz

Nenhuma escrita é dada por boa pela própria operação de escrita. A prova vem do
lado somente-leitura, que existe e está validado no MasterTool X:

```text
varredura da arvore (probe 21)   antes e depois, comparadas
export textual / PLCopen         conteudo do que foi criado
indice ST                        simbolos e referencias
compilacao offline               build(), erros e avisos coletados
```

O que não puder ser verificado por esse lado **não pode ser escrito**. É a
regra que mantém a trilha auditável: escrita sem verificação independente é
mudança sem evidência.

### Diff estrutural

Compara o **`.project`**, nunca a pasta: os `.opt` são reescritos a cada
abertura e acusariam mudança inexistente. E precisa tratar:

- **objeto transiente** — `is_transient_object` e
  `find_ignore_transient_objects` são conceito **novo** do MasterTool X
  (`docs/27` §6). Ignorá-los produz criação e remoção fantasma;
- **`object_guid` não é identidade estável** entre sessões (`docs/22`).
  Comparar por `name` e `type_guid`.

### Valor de teste

**Um valor de teste igual ao default não é evidência.** Achado da sessão de W0:
limites passados por argumento coincidiram com os defaults do probe e tornaram
o resultado inconclusivo. Todo parâmetro verificável usa valor impossível de
confundir com o padrão.

### Artefato de execução real

Coletor de artefato filtra por `platform == "cli"`, não só por data: a suíte de
testes grava artefatos de mesmo nome, em CPython, dentro de
`workspace/logs` (`docs/27` §9).

## 10. Rollback

A unidade de rollback é o **projeto**, não a operação: `create_*` devolve o
objeto **já inserido na árvore**, sem passo de confirmação — não existe
"desfazer" transacional na API.

```text
falhou qualquer passo    -> a copia de trabalho e DESCARTADA inteira
                            nunca "desfazer" operacao a operacao
promocao da copia        -> so apos verificacao aprovada e confirmacao humana
o estado anterior        -> preservado pelo arquivo de entrada, nunca sobrescrito
```

## 11. Critérios de aborto

Aborta imediatamente, sem tentar contornar:

```text
DIALOGO de conversao, atualizacao de versao, recuperacao, biblioteca ausente,
mudanca de compiler version, instalacao ou substituicao de device, login,
conexao, ou salvamento nao previsto no plano

operacao fora do plano          API fora da allowlist
hash da base alterado           projeto-base aberto por engano
processo orfao apos encerrar    artefato ausente ou ilegivel
instalacao diferente da esperada
```

Diálogo é cancelado e **registrado**, com o texto que apareceu. Um diálogo não
registrado apaga a única evidência de que a sessão encontrou o inesperado.

## 12. Trilha de auditoria

Cada sessão de escrita grava, fora do repositório:

```text
plano de alteracao                     manifesto da sessao
SHA-256 de base e copia, antes/depois  comando exato de cada execucao
duracao, exit code, processos orfaos   argv cru recebido pelo script
artefatos de cada probe                arquivos irmaos criados
diff estrutural antes/depois           saida da compilacao
observacao humana do que apareceu na tela
```

O último item não é dispensável e nenhum script o produz.

## 13. A primeira mutação — limites de W1

Quando autorizada, e **somente então**, a primeira escrita se limita a:

```text
criar GVL vazia
criar POU ST vazia do tipo PROGRAM
preencher conteudo minimo
save_as para arquivo NOVO
fechar e reabrir
verificar pelo lado read-only
compilar offline
```

Fora de escopo na primeira mutação, por contrato: Ladder e qualquer linguagem
gráfica, hardware, dispositivos, bibliotecas, tasks, DUTs, `FUNCTION_BLOCK`,
`FUNCTION` e projeto existente.

**Não combinar comprovação read-only e primeira mutação na mesma sessão.**

## 14. O gate

Este contrato não abre nada. Autorizar uma fase exige, nesta ordem:

```text
1. plano da fase escrito e aprovado
2. allowlist revisada contra o catalogo de docs/27 §7, nome a nome
3. decisao humana explicita de ATIVAR UMA FASE CONTROLADA
   (nunca de trocar READ_ONLY_PHASE, que permanece True)
4. commit ISOLADO contendo a fase e a allowlist
5. testes estruturais do gate NO MESMO COMMIT
6. NENHUMA implementacao de probe nesse commit
7. fechamento automatico de tudo que nao esteja expressamente autorizado
```

O passo 3 mudou de forma em `b8ad7bb`, e a mudança é substantiva: **trocar
`READ_ONLY_PHASE` para `False` autorizaria de uma vez as sete operações
legadas**, que é precisamente a abertura genérica que este contrato existe para
impedir. A autorização passa a nomear a fase, e a fase nomeia as operações.

O passo 5 anda junto do 4 porque a allowlist sem teste é promessa: são os
testes estruturais que provam que a autorização é literal, restrita à fase e
fail-closed. Separá-los deixaria a garantia sem verificação até algum commit
futuro.

O passo 6 existe para que a autorização apareça no histórico como decisão
datada, e não como linha perdida dentro de um slice de funcionalidade.

### Guarda adjacente à chamada

Autorizar a fase **não** basta. Cada chamada mutável carrega a sua própria
guarda, imediatamente antes da invocação real — ver `docs/29` §W1.1. Validar a
fase só no início do script deixaria todo o corpo dele implicitamente
autorizado.

### Fases seguintes

Cada uma exige o seu próprio commit isolado, com o mesmo rito:

```text
W1.2  acrescentara create_program (ou create_pou, conforme a interface real)
W1.3  acrescentara replace
W1.4  acrescentara build
```

`save_as` permanece autorizado **somente nas fases que explicitamente
precisarem dele**. Nenhuma dessas autorizações é antecipada aqui.

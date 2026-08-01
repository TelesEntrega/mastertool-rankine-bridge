# W1.4 — execução da autoria integrada com build

> Registro de execução. `run-019`, sobre o **projeto-base real do cliente**
> (`TemplateExemplo v1.project`, com cartões de I/O). É o marco que encerra W1.

## 1. Veredito

### O sistema cria, preenche, persiste e compila um projeto lógico em ST no MasterTool X

A cadeia inteira rodou numa sessão de autoria e duas leituras independentes:

```text
create_gvl → create_program → replace ×3 → save_as → reabrir → build → verificar
```

`integration_verified`. Zero erros de compilação, zero avisos, árvore com
exatamente os dois objetos previstos e nada mais.

## 2. Números medidos

| Grandeza | Valor |
| --- | --- |
| Template | `TemplateExemplo v1.project`, `596625796e4e…d1d815f5`, **elegível** desde a `run-018` |
| Saída | `W1-A5.project`, `6b3d11d1841879492ab127ea804cd17c4a295e4a1c19ec92b4d167a1e6b34cda` |
| Mutações | **6** — `create_gvl`, `create_program`, 3× `replace`, `save_as` |
| Build | `build_verified` — **0 erros, 0 avisos**, 8 informações |
| Output alterado pelo build | **não** — hash idêntico antes e depois |
| Árvore | 42 → **44** nós |
| Adicionados | `GVL_AI_TESTE`, `PRG_AI_TESTE` |
| `unexpected_additions` · `missing` | `[]` · `[]` |

<caption>

**Como ler:** "output não alterado pelo build" é medição, não suposição — o
probe calcula o SHA-256 do arquivo antes e depois de compilar. Importa porque
um build que reescreve o `.project` tornaria o artefato aprovado diferente do
artefato verificado, e ninguém saberia qual dos dois foi para produção.

</caption>

## 3. As três lacunas que a execução fechou

### A fonte das mensagens de compilação

`docs/32` registrava que nenhum acessor de mensagens estava catalogado, e o
probe 40 se recusava a declarar "sem erro" sem ter lido mensagem alguma —
parando em `messages_unavailable`. A recusa estava certa e foi ela que forçou
a busca.

Quem respondeu foi o stub do próprio `build()`
(`ScriptApplication.pyi` L41-49): *"You can use the System.get_messages and
System.get_message_objects calls to check whether any messages were added"*.
**A lacuna era do catálogo, não da API** — o mesmo diagnóstico do
`compiler_version`.

**Iterar as categorias é essencial.** O default de `get_message_objects` é a
categoria `ScriptMessage`, onde o próprio script escreve com `write_message`.
As mensagens de compilação vivem em outra categoria, e usar o default
devolveria vazio — vazio que leria como "build sem erro".

### Dois `TypeError`, da mesma família do que reprovou a `run-005`

| chamada | erro medido | resolução |
| --- | --- | --- |
| `get_message_objects(categoria, …)` | `expected str, got Guid` | conversão explícita **antes** da chamada |
| `severities` como inteiro | `expected Severity, got long` | **omitir** — o default do produto já é "todas" |

<caption>

**Como ler:** a `run-005` reprovou porque o plano trazia texto e a API exigia
`Nullable<Guid>`. Aqui é o inverso — a API **devolve** `Guid` e a outra exige
texto. A lição é a mesma: conversão explícita, na precondição, nunca entre a
guarda e a chamada.

</caption>

Omitir `severities` é mais correto que construir o enum por adivinhação: o
stub declara o default como `0xFFFFFFFF`, *"all severities are returned"* — o
default já é a intenção.

### A tabela de severidade estava incompleta, e a reprovação estava certa

Com as mensagens finalmente lidas, a `run-019` classificou as oito como
`unclassified` e **reprovou** — inclusive `Compile complete -- 0 errors, 0
warnings`. Faltava `Text`, o quinto membro do enum.

O comportamento estava certo: severidade que a tabela não conhece **não pode**
virar aviso por conveniência, senão um erro desconhecido passaria por
aprovado. O defeito era a tabela, não a regra. `Text` entra como informação e
**depois** de `error` e `warning` — a comparação é por substring, e uma
mensagem de erro que contivesse a palavra não pode ser rebaixada.

## 4. O defeito de operação, e a correção

`CloseMainWindow()` **não fecha** a janela nesta fase: compilar deixa o
projeto alterado em memória, o pedido de fechar cai num diálogo modal de
salvar, e a janela fica aberta. O operador teve de clicar "Não" **três vezes
seguidas**, porque eu relançava sem corrigir a causa.

`system.exit(0)` — *"shuts down the engine and exits the process"*
(`ScriptSystem.pyi` L143-157) — encerra sem passar pelo diálogo. Chamado
**depois** de os artefatos estarem no disco.

Não é `Stop-Process` disfarçado: aquilo mata o processo de fora e pode
interromper gravação; isto é o próprio produto se encerrando por API
documentada. Efeito medido: **22,7 s** contra 71–133 s, e o postsave ainda
rodou na sequência.

O wrapper também ganhou o aviso **antes** do lançamento — a lição de W1.5 que
eu não tinha replicado aqui.

## 5. O que sustentou a execução

**A elegibilidade não foi presumida.** O wrapper exige o artefato de
qualificação e recusa template inelegível; campo ausente também recusa. O
`TemplateExemplo v1` só passou porque `compiler_version` (`run-012`) e o inventário de 17
bibliotecas (`run-016`) tinham sido **medidos**.

**O prefixo `GVL_AI_TESTE.` era obrigatório**, por causa do pragma
`qualified_only` que a GVL carrega desde o nascimento — medido em W1.1. Sem
ele o build falharia, e a falha seria sobre o **conteúdo**, não sobre a
capacidade de escrever.

## 6. Limites

**O que a evidência comprova:** que a cadeia criação → escrita → persistência
→ reabertura → compilação funciona de ponta a ponta sobre um projeto
industrial real, com diff estrutural exato e sem erro de compilação.

**O que exige medição em campo:**

- **Um objeto de cada família.** Uma GVL e um PROGRAM. `FUNCTION_BLOCK`,
  `FUNCTION` e DUT têm texto de nascimento medido (W1.5), mas **nunca foram
  criados numa cadeia com build**.
- **Nenhuma Task e nenhum Program Call.** O programa compila; **não há
  evidência de que o CLP o executaria**.
- **DUT continua bloqueado** por falta de catálogo do enum `DutType`.
- **As 17 bibliotecas são todas placeholder.** Resolvem para versão concreta
  em tempo de compilação, e este build não fixa qual — dois builds em máquinas
  diferentes podem resolver diferente.
- ~~**Determinismo não foi medido.**~~ **MEDIDO** — cinco gerações da mesma
  spec sobre cópias novas produziram cinco arquivos de bytes distintos e um
  único projeto, com os dez pares equivalentes. Ver `docs/40`.

## 7. Estado

`W1_4_INTEGRATED_BUILD` foi **encerrada** em commit próprio.
`CONTROLLED_WRITE_PHASE = None`, `READ_ONLY_PHASE = True`. `build` voltou a
ser proibido: foi autorizado **uma** vez, para este marco.

**W1 está completo.** O que vem depois — famílias IEC na cadeia com build,
Task e Program Call, planner e executor — é fase própria, com allowlist
própria e gate próprio.

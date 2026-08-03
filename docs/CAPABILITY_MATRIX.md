# Matriz de capacidades

> **NORMATIVO E VIGENTE.** Fonte da escala de maturidade citada por
> [`ROADMAP.md`](ROADMAP.md) §2 e resumida por [`CURRENT_STATUS.md`](CURRENT_STATUS.md)
> §2. Onde este documento e `CURRENT_STATUS.md` divergirem em contagem, é
> defeito deste documento — `CURRENT_STATUS.md` é a fonte canônica do estado
> vigente. Modelo de segurança normativo: [`SAFETY_MODEL.md`](SAFETY_MODEL.md).

## 0. Como este documento foi construído

A lista de operações de autoria vem de
`src/mastertool_bridge/planner/planner.py:176-318`, o dicionário
`EXECUTOR_CONTRACT` — a única fonte autorizada do que o executor sabe fazer.
Cada entrada carrega três campos que respondem perguntas diferentes:

```text
cataloged      a API existe no registro literal de docs/27 §7
field_proven   a operação foi EXERCIDA contra o produto real, numa cadeia
               que persistiu (save_as) e compilou (build), com artefato citado
mutating       o passo muta o projeto (True) ou é só leitura de verificação
               (False, ex.: reopen, verify)
```

`EXECUTOR_CONTRACT` tem **14 chaves** — as 14 operações de `PLAN_OPERATIONS`
(`planner.py:125-140`), e é esse o número que `CURRENT_STATUS.md` publica.
Deste total, **doze mutam** o produto (`create_gvl`, `create_program`,
`create_function`, `create_function_block`, `create_dut`, `create_task`,
`create_program_call`, `bind_program_to_task`, `configure_task`, `replace`,
`save_as`, `build`) e **duas não** (`reopen`, `verify`, que são leitura de
verificação). As 14 linhas da primeira tabela abaixo cobrem o dicionário
inteiro, e a coluna `mutating` diz de qual grupo cada uma é.

> Registros anteriores deste projeto diziam **treze** operações. O número vem
> do `EXECUTOR_CONTRACT`, e uma guarda automatizada
> (`tests/unit/test_documentacao_coerente.py`) agora reprova quando a contagem
> publicada diverge do código — contagem escrita à mão envelhece.

**Todas as 14 entradas têm `field_proven: True`.** Nenhuma tem `field_proven:
False` hoje — os candidatos que um dia estiveram bloqueados (`create_dut`,
`create_task`) foram promovidos por execução real (`docs/46`, `docs/48`) antes
deste documento existir. Isso não eleva a maturidade: `field_proven` é o teto
atual por regra do roadmap, não por limitação de medição.

## 1. Por que nada está acima de `field_proven`

> **Regra normativa (ROADMAP.md §2):** o planner de produção emite apenas
> operações `production_qualified`; os níveis inferiores existem para
> laboratório. Hoje **nada** no sistema passa de `field_proven`, porque
> **repetibilidade (R1) não foi executada.**

A razão não é falta de trabalho offline — é estrutural: promover uma operação
acima de `field_proven` exige **execução real do MasterTool, com operador
humano presente**, e nenhuma quantidade de refatoração, teste unitário ou
revisão de código substitui isso. Trabalho offline constrói o instrumento de
medida (planner, executor, validador, schemas); a medição em si é sessão de
campo. `repeatable` exigiria ≥10 execuções independentes com critérios
negativos comprovados (`ROADMAP.md` §4, R1) — a fábrica só foi repetida
**duas vezes** até hoje (`docs/44`, `docs/47`), o que mede determinismo em
n=2, não repetibilidade em produção.

> **PROMOÇÃO DE 2026-08-02.** Onze operações passaram de `field_proven` para
> `repeatable` com a qualificação R1 N=10 (`docs/50`): dez execuções
> independentes da mesma spec, dez builds verificados sem aviso do fabricante,
> 10/10 equivalentes e independência limpa nos 45 pares.
>
> **As três que faltavam fecharam no mesmo dia** (`docs/51`): um segundo lote
> N=10, com spec que **cria** task, promoveu `create_task`,
> `bind_program_to_task` e `configure_task`. **As catorze operações do
> `EXECUTOR_CONTRACT` estão `repeatable`.**
>
> Nenhuma operação está acima de `repeatable`: `template_qualified` exige o
> perfil do template sem lacuna, e duas continuam abertas (inventário de
> dispositivos e library lock).

## 2. Operações de autoria (mutação de projeto)

| Operação | O que faz | Maturidade | Evidência (doc + run) | Qualificada em | Limites conhecidos |
|---|---|---|---|---|---|
| `create_dut` | Cria DUT `STRUCT` ou `ENUM`, persiste e sobrevive a build (muta) | **`repeatable`** | `docs/46` (W6, run-033) + `docs/50` (R1 N=10, 10 runs) | MasterTool X 4.1.0.11, `TemplateExemplo v1.project` (596625…815f5) | Só `STRUCT`/`ENUM` — `Alias`/`Union` do enum `DutType` nunca foram exercidos (`docs/45` §4) |
| `create_gvl` | Cria GVL vazia, persiste (muta) | **`repeatable`** | `docs/33` (W1.3A), `docs/37` (W1.4, run-019) + `docs/50` (R1 N=10, 10 runs) | MasterTool X 4.1.0.11, base anterior (`6183d01d…5540dd3`) e `TemplateExemplo v1.project` | Texto canônico com pragma `qualified_only` medido; sem esse pragma o `replace` o apagaria |
| `create_function` | Cria `FUNCTION` tipada com `return_type`, instanciável e chamável (muta) | **`repeatable`** | `docs/43` (W5, run-028) + `docs/50` (R1 N=10, 10 runs) | MasterTool X 4.1.0.11 | Prova exige cadeia completa (`create`→`replace`→`save_as`→reabrir→`build`); W1.5 (`docs/35`) só leu o nascimento sem essa cadeia e não contava como prova |
| `create_function_block` | Cria `FUNCTION_BLOCK`, instanciável e chamável (muta) | **`repeatable`** | `docs/43` (W5, run-028) + `docs/50` (R1 N=10, 10 runs) | MasterTool X 4.1.0.11 | Sem `base_type`/`interfaces`/métodos/propriedades — a spec não tem campo para isso (`project_spec.schema.json` §function_block) |
| `create_program` | Cria `PROGRAM` ST vazio (muta) | **`repeatable`** | `docs/30` (W1.2), `docs/37` (W1.4, run-019) + `docs/50` (R1 N=10, 10 runs) | MasterTool X 4.1.0.11 | Texto canônico sem pragma, sem cabeçalho — medido, não presumido |
| `create_task` | Cria task de configuração (muta) | **`repeatable`** | `docs/48` (W8, run-036) + `docs/51` (R1-TASK N=10) | MasterTool X 4.1.0.11 | Só criar uma task vazia gerava aviso do fabricante; a prova válida exige `bind_program_to_task` na mesma cadeia |
| `create_program_call` | Vincula chamada de PROGRAM **dentro** de um POU do Perfil de Projeto, via `replace` (idiomático; muta) | **`repeatable`** | `docs/41` (W3, run-026) + `docs/50` (R1 N=10, 10 runs) | MasterTool X 4.1.0.11 | Existe forma alternativa (`MainTask.pous.add`) medida em `docs/39`/run-021, mas o fabricante desaconselha; o planner só emite a idiomática |
| `bind_program_to_task` | Vincula POU a uma task **criada pela spec**, via `ScriptPouObjectCollection.add` (muta) | **`repeatable`** | `docs/48` (W8, run-036) + `docs/51` (R1-TASK N=10) | MasterTool X 4.1.0.11 | Só serve para task criada pela própria spec — nunca uma task preexistente que a spec não gerou |
| `configure_task` | Escreve `kind_of_task`, `interval`, `interval_unit`, `priority` por atribuição de propriedade (muta) | **`repeatable`** | `docs/49` (W9, run-037) + `docs/51` (R1-TASK N=10) | MasterTool X 4.1.0.11 | Só os 4 campos catalogados; `event`, `external_event`, `core_binding`, `parent_synchron_task` e `watchdog.*` estão fora — sem receptor/verificação escritos |
| `replace` | Substitui documento textual (declaração/implementação) inteiro (muta). **Duas classes de alvo, ambas medidas:** objeto criado pelo próprio plano, e objeto **preexistente** — este com o sha256 do texto anterior conferido no campo, no instante anterior à sobrescrita | **`repeatable`** | criado: `docs/33` (W1.3A), `docs/34` (W1.3B), `docs/37` (W1.4) + `docs/50` (R1 N=10). Preexistente: `docs/52` (W10) + `docs/53` (N=10) | MasterTool X 4.1.0.11 | Substitui o documento inteiro — sem `insert`/`replace_line` por offset em produção. Sobre alvo preexistente, o "antes" tem que vir de inventário MEDIDO (`verify-modifications` recusa hash sem procedência). **Reversível nas duas direções** (`docs/54` prova, `docs/55` N=10 da reversão, `docs/56` N=10 do desfazer-a-reversão): o ciclo alterar → reverter → re-alterar fecha, e o revertido é indistinguível do template. O único alvo exercido tem texto anterior **vazio** — a conferência nunca rodou contra conteúdo real |
| `save_as` | Persiste em arquivo novo, nunca sobrescreve a entrada (muta) | **`repeatable`** | `docs/33`, `docs/37`, `docs/39`, `docs/41` + `docs/50` (R1 N=10, 10 runs) | MasterTool X 4.1.0.11 | `save()` nunca é chamado pelo executor — só `save_as` |
| `reopen` | Reabre o projeto salvo, numa sessão nova, para verificação independente (não muta) | **`repeatable`** | `docs/37` (postsave), `docs/41` + `docs/50` (R1 N=10, 10 runs) | MasterTool X 4.1.0.11 | É o que distingue "existiu na sessão" de "foi persistido" (`docs/32` §3) |
| `build` | Compila offline e coleta mensagens (muta) | **`repeatable`** | `docs/37` (run-019), `docs/39` (run-021), `docs/41` (run-026) + `docs/50` (R1 N=10, 10 runs) | MasterTool X 4.1.0.11 | Mensagens lidas por `system.get_message_objects`; ausência de mensagem nunca é aprovação (`no_build_messages`, `SAFETY_MODEL.md` §6) |
| `verify` | Compara árvore/texto antes e depois via analisador read-only (não muta) | **`repeatable`** | `docs/37`, `docs/41` + `docs/50` (R1 N=10, 10 runs) | MasterTool X 4.1.0.11 | Só filhos diretos (`get_children(False)`) — POUs dentro de `UserPOUs`/`SystemPOUs` ficam fora do diff estrutural (`LIMIT_DIRECT_CHILDREN_ONLY`, `planner.py:415-419`); não existe API para reler a linguagem de um objeto existente (`LIMIT_LANGUAGE_NOT_READABLE`) |

<caption>

**Como ler esta tabela:** as catorze operações do `EXECUTOR_CONTRACT` estão em
`repeatable` desde os dois lotes N=10 (`docs/50`, `docs/51`). Nenhuma sobe daí:
`template_qualified` exige o perfil do template **sem lacuna**, e duas seguem
abertas (inventário de dispositivos e library lock); `version_qualified` exige
mais de uma versão do MasterTool, e só existe uma medida. O `replace` tem **uma** linha e não duas, ainda
que W10 tenha medido uma classe de alvo nova: o perfil deriva grau por
**operação**, e alvo preexistente não é verbo novo. As vinte runs que
sustentam o grau — dez de `docs/50` e dez de `docs/53` — estão no perfil.
"Qualificada em" cita produto+versão+template pelo mesmo motivo que
`docs/COMPATIBILITY_MATRIX.md` existe: uma operação provada no MT9000 4.1.0.11
não se presume provada em nenhum outro produto ou versão.

</caption>

### Determinismo medido — separado da tabela acima, porque não é uma operação

Duas medições de determinismo existem, e nenhuma das duas eleva maturidade:

| Medição | Runs | O que mediu | Resultado |
|---|---|---|---|
| `docs/40` | 5 gerações da mesma spec (GVL+PROGRAM) | equivalência de conteúdo, não igualdade de bytes | equivalente nas 5 |
| `docs/44` | `run-029`/`run-030`, fábrica de 3 objetos | mesmo plano (hash idêntico), árvore idêntica (45 nós), texto idêntico, `.project` com hash diferente (GUID/timestamp) | equivalente |
| `docs/47` | `run-034`/`run-035`, fábrica de 7 objetos, 5 famílias | mesmo plano (24 passos, hash idêntico), 7/7 verificados, `object_guid` distintos (prova de independência) | equivalente |

n máximo medido é **2** execuções independentes por spec. R1 exige **≥10** —
a lacuna é de escala de medição, não de mecanismo.

## 3. Capacidades de leitura e análise

| Capacidade | O que faz | Maturidade | Evidência (doc + run) | Qualificada em | Limites conhecidos |
|---|---|---|---|---|---|
| Varredura completa da árvore (tree scan) | `get_children(False)` recursivo, limites por argumento, isolamento de erro por ramo | `field_proven` | `docs/11` (117 nós, 8/8 checksums, `ExemploPlanta V1.0.project`), `docs/22`/`docs/27` §9 (probe 21 no MT9000, 3 raízes/34 nós, 0 erros) | MasterTool IEC XE 3.63 (qualificado, projeto real); MasterTool X 4.1.0.11 (exercido uma vez, cópia descartável) | Só filhos diretos por chamada (`get_children(False)`); `object_guid` não é identidade estável entre sessões (`docs/18` ponto 5) |
| Export textual (declaração/implementação) | Extrai `IScriptTextDocument` por objeto, preservação exata verificada por amostragem SHA-256 | `field_proven` | `docs/12` (92 nós, 158/158 checksums, 66.360 caracteres, `ExemploPlanta V1.0.project`) | MasterTool IEC XE 3.63 (projeto real) | Não lê a linguagem de um objeto existente (`LIMIT_LANGUAGE_NOT_READABLE`) |
| Índice ST (símbolos, DUT, referências, read/write, chamadas) | `StaticProjectIndexer` opera só sobre export já em disco, nunca reabre o MasterTool | `field_proven` | `docs/13` (12 commits verificados, smoke contra `ExemploPlanta V1.0.project`) | Independente de produto — opera sobre arquivo já exportado | Detecta `EXTENDS`/`IMPLEMENTS` como texto bruto (`declaration_parser.py:164-199`), mas não resolve semântica de interface/herança |
| Export PLCopen (Ladder) | `export_xml(stPath, False, False, False)` → PLCopen XML tc6_0200 | `field_proven` | `docs/17` (42 elementos, MasterTool IEC XE 3.63), `docs/23` (export por dispositivo) | MasterTool IEC XE 3.63 | Export do projeto **inteiro** é monolítico e falha em silêncio — um único devdesc ausente aborta o arquivo sem fechar `</project>` (`docs/26`); export por dispositivo isola a falha |
| Inventário de dispositivo | `device_inventory.py` + `tools/build_device_inventory.py`, offline, sobre exports já feitos | `field_proven` | `docs/25` (35/35 dispositivos, 1894 parâmetros) | MasterTool IEC XE 3.63/3.70 (repositório de dispositivos é por versão instalada) | `device_parameters` (API) devolve `Count=0` sempre — resultado vazio ≠ ausência de configuração; só o export XML tem os valores |
| Estrutura/topologia Ladder | `structure_map` → `ladder_parser` → `canonical_model` → `logical_topology` | `field_proven` | `docs/17`, `docs/20` (contrato), 4 redes/66 nós/26 arestas sobre o artefato de referência (`docs/18` "Artefato de referência da POU real") | MasterTool IEC XE 3.63 (artefato de referência real) | **Semântica** (leituras/escritas/chamadas por network) está em backlog — contrato `docs/21` íntegro, não implementado |

## 4. Recusado explicitamente

O sistema detecta e recusa, com diagnóstico nomeado, em vez de aceitar em
silêncio e produzir um plano que mentiria sobre o que executa:

| O que é recusado | Onde vive a recusa | Diagnóstico |
|---|---|---|
| DUT `Alias`/`Union` (membros medidos do enum `DutType` — `docs/45`) | `project_spec.schema.json:65` (`"enum": ["STRUCT", "ENUM"]`), `spec/validator.py:289-293` | schema rejeita valor fora do enum; validador repete a checagem com mensagem `"{kind!r} inválido, use 'STRUCT' ou 'ENUM'"` |
| `FUNCTION_BLOCK` com `base_type`, `interfaces`, métodos, propriedades, ações/transições | `project_spec.schema.json:95-106` (`function_block` não declara esses campos, `"additionalProperties": false`) | rejeição de schema — campo desconhecido não passa; espelhado em `spec/validator.py:270-272` (`"campo(s) desconhecido(s), fail-closed"`) |
| Task `Event`, `Status`, `ExternalEvent` (membros medidos do enum `KindOfTask` — `docs/45`) | `spec/validator.py:439-482` (`_KINDS_OF_TASK_SUPPORTED = ("Cyclic", "Freewheeling")`) | `"'{kind}' exige um gatilho (event ou external_event) que esta spec não sabe escrever"` |
| `watchdog.*` de task | `scripts/mastertool/common/safety.py:109,145` (comentário normativo) — nunca entra em `MASTERTOOL_PROPERTY_WRITES` | ausência deliberada da allowlist de propriedade — nome nunca alcança `assert_controlled_property_write_allowed`; recusado por não estar catalogado, fail-closed |
| `event`, `external_event`, `core_binding`, `parent_synchron_task` (propriedades de task) | `safety.py:107-113` — settable no stub, fora de `MASTERTOOL_PROPERTY_WRITES` | mesma classe de recusa que `watchdog.*`: catalogado no stub, deliberadamente fora da allowlist |
| `download_missing_libraries` | `safety.py:82` está em `MASTERTOOL_MUTATING_OPERATIONS` (catalogado) mas **nenhuma** operação de `PLAN_OPERATIONS`/`EXECUTOR_CONTRACT` a consome — inalcançável pelo planner; proibição normativa em `docs/28` §140-141 e `SAFETY_MODEL.md` §2 ("baixar biblioteca é mudar a resolução de dependência sem declaração") | recusa em duas camadas: nenhum caminho de plano a alcança, e o contrato a proíbe nominalmente |
| `set_compilerversion_to_newest` | mesma situação: catalogado em `safety.py:82`, fora de `EXECUTOR_CONTRACT`; proibição em `docs/28` §142 e `SAFETY_MODEL.md` §2 | idem — inalcançável pelo planner e proibido pelo contrato |
| `ScriptPromptHandling.SuppressPrompts` | `docs/27` §8 item 1, `docs/28` §140, `SAFETY_MODEL.md` §2 | proibição contratual — `LogPrompts` é o único valor aceitável; não há caminho no planner que sequer nomeie `ScriptPromptHandling` |
| `configure_existing_task` (alterar propriedade de task PREEXISTENTE) | metade do host escrita (`spec/task_property_source.py`, `verify-modifications`); o executor **não tem** a busca por task já existente | recusa por operação inalcançável: nenhum passo do planner a emite. O host sabe conferir o "antes"; ninguém sabe aplicar o "depois" |
| `rename_object` | `rename` está na lista de membros PROIBIDOS do executor | recusa nominal, antes de qualquer fase |
| Operações permanentemente fora de escopo (online, download, force, hardware) | `safety.py:22-36` (`FORBIDDEN_OPERATIONS`), espelhado em `config/safety-policy.yaml` | bloqueio incondicional, sem fase, sem allowlist — `assert_operation_allowed` recusa antes de qualquer outra checagem |

## 5. Não suportado e não detectado

Esta seção é honesta por construção: lista o que o sistema **não sabe
recusar com diagnóstico próprio** — porque não há vocabulário, campo de
schema ou verificação que sequer reconheça o pedido. Pedir isso hoje resulta
em erro de schema genérico (campo desconhecido) ou, pior, em silêncio se o
pedido nunca chegar a tocar um caminho validado.

- **`PersistentVars`, `actions`/`transitions` textuais, `getter`/`setter`,
  `namespaces`, atributos e pragmas customizados** — fora do schema
  (`project_spec.schema.json`) e fora do vocabulário de `EXECUTOR_CONTRACT`.
  `create_persistentvars` está **catalogado** em `safety.py:65` mas não tem
  operação correspondente no planner — mesma situação de
  `download_missing_libraries`: alcançável pelo produto, inalcançável pela
  spec.
- **Bibliotecas reais** — as 17 bibliotecas do template são todas
  *placeholder* (`CURRENT_STATUS.md` §2); nenhum build fixa a versão
  resolvida, e não há Library Lock formal (contrato previsto para R3,
  `ROADMAP.md` §4). Detectar biblioteca ausente versus incompatível não está
  implementado.
- **Renomear objeto** (`rename_object`) — sem operação no planner; adiável
  por decisão do roadmap (R2) por risco de efeito indireto difícil de
  controlar (`ROADMAP.md` §4).
- **FBD e SFC**, em leitura ou autoria — nenhum parser, nenhum modelo
  canônico. Reservado para R5 (leitura) e R7 (autoria), ambos não
  iniciados.
- **Semântica Ladder** (leituras/escritas/chamadas por network, resolução
  simbólica) — contrato `docs/21` escrito e íntegro, implementação em
  backlog (R4).
- **Unificação ST + Ladder num grafo só** — depende de R4/R5, não existe
  hoje.
- **Hardware e I/O** — leitura de racks/cartões/canais/endereçamento e
  validações (endereço duplicado, canal sem variável) não implementadas;
  reservado para R8. Escrita de hardware está **fora do executor principal
  no v1.0** por decisão (`ROADMAP.md` §R8), não por lacuna a fechar.
- **Change set com estados e aprovação/rollback executáveis** —
  `changes/approval.py` e `changes/package_builder.py` levantam
  `NotImplementedPhaseError` (`CURRENT_STATUS.md` §4); reservado para R6.
- **Diff semântico** — `diff/semantic_diff.py` levanta
  `NotImplementedPhaseError`; hoje o diff é textual e estrutural, nunca
  semântico (`CURRENT_STATUS.md` §4).
- **Qualquer objeto sob mais de um nível de aninhamento** — o planner nunca
  emite `create_folder` nem aninha objeto em objeto, por decisão de
  desenho ligada a `LIMIT_DIRECT_CHILDREN_ONLY` (`planner.py:415-419`), não
  por incapacidade da API do produto (que expõe `create_folder`).
- **Outra instalação, outra máquina, outro operador** — nada foi medido fora
  desta máquina e desta sessão; `docs/COMPATIBILITY_MATRIX.md` documenta o
  escopo exato do que foi exercido.

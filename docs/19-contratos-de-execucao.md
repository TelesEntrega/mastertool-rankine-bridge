# Contratos de execução — estados, schemas e campos comuns

Frente 3 da consolidação. Define os contratos estáveis que as cinco operações
supervisionadas já cumprem **de fato**, separa o que é igual do que é
diferente por motivo real, e nomeia as divergências que precisam ser
resolvidas **antes** de qualquer abstração.

A ordem não é acidental: abstrair os probes 16–20 sobre schemas ainda
inconsistentes consolidaria diferenças acidentais como se fossem contrato.
Este documento existe para que a frente 1 saiba o que pode centralizar.

Tudo aqui foi medido no código e nos artefatos reais, não presumido.

## 1. Estado operacional × resultado científico

**O contrato mais importante do projeto, e o mais fácil de quebrar.**

Um resultado científico inconclusivo **não é** falha operacional. Uma
investigação que roda corretamente e descobre que o canal não funciona é uma
execução `completed` com veredito negativo — não uma execução `failed`.

Já vigente para a exportação (`docs/16`, seção "Estado operacional ×
resultado científico"):

| `export_result` | significado | `final_state` |
|---|---|---|
| `P1_graphical_body_present` | XML com corpo gráfico | `completed` |
| `P2_declaration_only` | PLCopen válido sem corpo gráfico | `completed` |
| `P3_no_output` | nada produzido | `completed` |
| `P4_unrecognized_format` | formato não reconhecido | `completed` |

Só produzem `failed`: `export_invocation_failed`, `project_copy_modified`,
`runtime_provenance_mismatch`, `target_identity_mismatch`,
`artifact_validation_failed`, `output_escaped_export_root`.

**Contrato geral:** toda operação de investigação separa dois eixos
independentes — *a execução foi íntegra?* (estado operacional) e *o que se
descobriu?* (resultado científico). Nenhum dos dois pode ser derivado do
outro. Um relatório que colapsa os dois num campo só destrói a distinção que
o projeto inteiro depende.

**Divergência a resolver:** as quatro operações read-only expressam o veredito
científico com vocabulário próprio cada uma (`abort_reason`, campos
`*_confirmed`, artefatos como `control-validation.json` e
`known-control-discovery.json`). Não há um campo comum equivalente ao
`export_result`. A frente 1 não pode inventar um vocabulário unificado por
conta própria — a taxonomia de cada canal é específica. O que **pode** ser
comum é a *forma*: um campo de veredito científico declarado, com valor de um
vocabulário fechado por operação, separado do estado operacional.

## 2. Estados

Dois níveis, hoje declarados em lugares diferentes:

| Nível | Onde | Valores |
|---|---|---|
| Terminal (host) | `automation/result_models.py: TERMINAL_STATES` | `completed`, `failed`, `needs_interaction` |
| Interno (`status.json`) | espalhado — ex.: `host_validation_revision.py: INTERNAL_PROVENANCE_STATE` | `scanning`, `probing_ladder_dynamic_surface`, `probing_ladder_extender_surface`, `provenance_validated`, … |

Os estados terminais têm fonte única e são validados na construção
(`SupervisedRunResult.__post_init__` levanta em estado desconhecido). **Os
estados internos não têm fonte única no lado Python** — aparecem como
literais em módulos diferentes e nos scripts IronPython.

**Contrato:** estado dedicado por operação permanece (`docs/16` justifica: cada
estado marca fronteira operacional real, permite distinguir timeout de falha
semântica e mantém artefato histórico autoexplicativo).

Um estado genérico com subestado seria regressão: apagaria a fronteira que
torna o artefato arquivado legível sem contexto.

**Resolvido** (`refactor: centralize supervised operation states`). O
vocabulário já existia completo no lado interno
(`run_status.py: VALID_STATES`, 15 estados); o que faltava era o **host**, que
só tinha os terminais e espalhava o resto como literal.

`src/mastertool_bridge/automation/run_states.py` é a fonte única do host: uma
constante por estado, `VALID_STATES`, `TERMINAL_STATES`, e as transições. Os
dois runtimes não podem se importar — IronPython 2.7 de um lado, CPython 3.11
do outro — então há duas declarações, e `tests/unit/test_run_states.py` falha
se divergirem, **inclusive na ordem**, que é o próprio fluxo esperado.
`result_models.TERMINAL_STATES` era uma terceira cópia e virou reexportação.

As transições em `OBSERVED_TRANSITIONS` são **evidência, não desenho**: foram
derivadas de 10 execuções reais arquivadas, lendo `status-history.jsonl`. O
que está lá aconteceu de fato. Transição legítima ainda não ocorrida
simplesmente não consta — ausência de observação não é prova de
impossibilidade, a mesma disciplina que o projeto aplica às APIs do MasterTool.
Por isso `unobserved_transitions()` **sinaliza** em vez de reprovar, e nada é
imposto no caminho de escrita: o runner interno continua a única autoridade
sobre o que grava em `status.json`. Impor validação de transição no caminho
que roda dentro do MasterTool exigiria testar em campo o que não pode ser
testado aqui.

Três estados existem no vocabulário e nunca apareceram num histórico real:
`created` e `mastertool_started` (escritos pelo host, antes de o runner
interno existir) e `needs_interaction` (nenhuma das 10 runs precisou de
intervenção). Ficam declarados em `NOT_YET_OBSERVED_STATES`.

**Nota sobre `probing_ladder_surface`:** não existe, e a ausência é decisão. O
probe 16 reusa `scanning` por não ter gate de validade próprio, ao contrário
dos probes 17, 18 e 19. Há teste que falha se alguém o criar por simetria, para
que a decisão seja revisada em vez de contornada.

## 3. Procedência

Centralizado e consistente — **o eixo mais saudável hoje**.

- `cli_probe_verify.check_provenance()` é a única implementação.
- Seção `runtime` do resultado carrega a evidência.
- Códigos: `runtime_provenance_missing`, `runtime_provenance_mismatch`.
- `ProvenanceCheckResult` (`result_models.py`) reusa o formato tal-e-qual, sem
  reinventar.

**Contrato:** toda operação emite seção `runtime` e passa por
`check_provenance()`. Ausência da seção reprova — foi o defeito `d418885`,
em que a seção nunca era emitida e **toda** run terminava `failed`.

**Não abstrair mais.** Já está certo.

## 4. Identidade do alvo

Os quatro `expected_*` (`target_node_id`, `expected_name`, `expected_guid`,
`expected_type_guid`) não são redundantes: cada um falha por um motivo
diferente (`docs/16`, seção 3.1). Todas as cinco operações validam identidade
e abortam com `target_identity_mismatch`.

**Divergência RESOLVIDA** (`fix: archive PLCopen export target identity`). O
registro histórico fica abaixo porque explica *por que* o artefato existe — e
porque a mesma assimetria pode reaparecer na próxima operação de escrita.

A exportação passou a emitir `target-identity.json`, escrito em três pontos e
coberto por `checksums.sha256`; ausência em run arquivada é aviso, não erro.
Ver `docs/16-supervised-runner-contract.md`, seção da exportação controlada.

**Como era antes — e é a divergência mais séria que este documento encontrou:**

| Operação | valida identidade | **arquiva** `target-identity.json` |
|---|---|---|
| probe 16 surface | sim | **sim** |
| probe 17 dynamic | sim | **sim** |
| probe 18 extender | sim | **sim** |
| probe 19 signature | sim | **sim** |
| **exportação controlada** | sim (`_check_identity`, `20_validate_controlled_plcopen_export.py:306`) | **NÃO** |

A exportação registra `target_identity_confirmed` no resultado e no
`report.md`, mas **não emite artefato de identidade próprio e checksummado**.
`invocation.json` carrega assinatura da chamada e argumentos — não identidade
do alvo.

Consequência: a única operação que **escreve** é a que tem a rastreabilidade
de alvo mais fraca no arquivo arquivado. Quem auditar uma exportação antiga
depende de texto de relatório, não de artefato verificável por checksum.

Isso é lacuna, não diferença essencial. **Deve ser corrigido antes da frente
1** — caso contrário a abstração congelaria a lacuna como se fosse contrato.

## 5. Safety declaration

Toda operação emite `safety-declaration.json`. A **forma** depende da classe
da operação, e essa distinção é correta e deve ser preservada:

**Classe read-only** (`LADDER_PROBE_SAFETY_DECLARATION_KEYS`) — 10 chaves,
todas obrigatoriamente `False`: `text_document_read`, `text_document_write`,
`export_called`, `import_called`, `save_called`, `build_called`,
`online_operation`, `download_called`, `force_called`, `project_modified`.

**Classe escrita controlada** (exportação) — a única em que campos `True` são
esperados:

- `PLCOPEN_EXPORT_SAFETY_TRUE_KEYS`: `export_xml_called`,
  `filesystem_output_written`
- `PLCOPEN_EXPORT_SAFETY_FALSE_KEYS`: `project_save_called`,
  `project_build_called`, `text_document_write_called`, `import_called`,
  `online_operation`, `download_called`, `force_called`
- `export_xml_call_count` ∈ {0, 1} — uma execução, uma invocação
- `filesystem_output_scope` == `authorized_disposable_export_root`
- a chave genérica `write_called` é **proibida** aqui: um XML é escrito, e a
  chave sugeriria o contrário

**Contrato:** *"uma declaração toda `False` na exportação seria tão errada
quanto uma declaração `True` num probe read-only"* — honestidade tem forma
diferente conforme o que a operação faz.

**O que a frente 1 pode centralizar:** o mecanismo (ler, parsear, reprovar
fail-closed em ausência/ilegibilidade) e a noção de *classe de operação*. **O
que não pode:** fundir os dois conjuntos de chaves num só schema permissivo.
Um schema que aceite as duas formas aceita uma exportação silenciosa e um
probe que escreveu.

## 6. Validação de artefatos — o núcleo comum, medido

Interseção calculada sobre as cinco tuplas `*_REQUIRED_FILENAMES`:

**Comum às 5 operações (4 arquivos):**
`checksums.sha256`, `diagnostics.json`, `report.md`, `safety-declaration.json`

**Comum às 4 read-only, ausente na exportação (2 arquivos):**
`manifest.json`, `target-identity.json`

Exclusivos por operação: 5 (probe 16), 6 (probe 17), 8 (probe 18),
6 (probe 19), 5 (exportação). Totais: 12, 14, 15, 12, 9.

Leitura honesta desses números: **o núcleo verdadeiramente comum é pequeno —
quatro arquivos.** A maior parte de cada conjunto é específica do canal
investigado, e deve continuar específica. Uma abstração que tente unificar
além dos quatro (mais os dois recuperáveis) estará inventando semelhança.

**Extraído** (`refactor: extract common supervised operation artifacts`).
`scripts/mastertool/common/artifacts.py` concentra o mecanismo — e só ele:

- `write_json_via_temp` / `write_text_via_temp` — escrevem um `.tmp`, removem o
  destino anterior e renomeiam o `.tmp` por cima; mesmo procedimento já
  documentado para `status.json`. O nome descreve o processo de propósito:
  IronPython 2.7 não tem `os.replace` e no Windows `os.rename` falha se o
  destino existir, então há uma janela entre remover e renomear em que o
  arquivo não existe — chamar isso de substituição indivisível seria descrever
  um comportamento que o procedimento não tem. A garantia real é mais estreita:
  o destino nunca fica com conteúdo pela metade, e o temporário é removido em
  qualquer falha, para não virar artefato fantasma no `checksums.sha256`
  seguinte. Para a janela, a defesa é o `status-history.jsonl` append-only;
- `write_checksums(root, output, exclude_dirs)` — o parâmetro de exclusão
  existe por uma divergência legítima: o probe 20 mantém `export-root/` fora,
  porque aquele conteúdo veio da API do MasterTool e tem hashes próprios em
  `created-artifacts.json`;
- `write_common_artifacts` — os quatro, nesta ordem, com checksums por último;
- `ArtifactWriteError` — carrega caminho e causa, para quem chama registrar
  diagnóstico em vez de propagar exceção crua.

O que **não** entrou: nenhum schema de safety declaration. A declaração chega
pronta de quem chama, e o módulo não sabe — nem deve saber — se a operação é
read-only ou de escrita controlada.

Equivalência verificada chamando `_write_artifacts` real dos cinco probes,
antes e depois, no mesmo diretório: **artefatos byte a byte idênticos nos
cinco**. `manifest.json`, `invocation.json`, `target-identity.json`,
`control-validation.json`, `created-artifacts.json` e `extension-items.json`
continuam fora do helper, sob responsabilidade de cada operação.

Sobre os dois ausentes na exportação:

- `target-identity.json` — **lacuna real**, ver seção 4. Corrigir.
- `manifest.json` — a exportação usa `invocation.json`, que cumpre papel
  análogo (metadados da operação) com conteúdo legitimamente diferente
  (assinatura e argumentos da chamada). Aqui a diferença **é** essencial:
  probe descreve o que sondou, exportação descreve o que invocou. Renomear um
  para o outro seria uniformidade cosmética destruindo significado.

## 7. Versionamento de schema — normalizado por família

**Resolvido** (`refactor: centralize schema versions by artifact family`), mas
*não* como este documento propunha na primeira redação. O inventário completo
mudou a conclusão, e o registro de por quê fica aqui.

O que a contagem sobre `src/` **e** `scripts/` mostrou:

| Valor escrito | Ocorrências | Arquivos |
|---|---|---|
| `"1.0"` (string) | 36 | 29 |
| inteiro | 7 | 6 |
| `"2.0"` (string) | 1 | 1 |

E os cinco JSON Schemas de `src/mastertool_bridge/schemas/` declaram
`"schema_version": {"type": "string"}`. A string não é descuido: é contrato
formalizado, cumprido por 29 arquivos — quase todos IronPython, rodando dentro
do MasterTool.

Converter tudo para inteiro exigiria alterar esses 29 arquivos, trocar o tipo
nos cinco JSON Schemas, invalidar a leitura de artefatos arquivados cobertos
por checksum, e decidir o que fazer com o `"2.0"` — que a regra "escreva
sempre 1" apagaria. Tudo isso **sem corrigir bug algum**: cada família é
internamente consistente, e nenhum leitor cruza a fronteira.

**Política adotada — versão é por família, nunca global:**

| Família | Tipo | Constante |
|---|---|---|
| Configuração de run | inteiro | `automation/config_models.py: SCHEMA_VERSION` |
| Resposta de consulta | inteiro | `indexer/query_response.py: SCHEMA_VERSION` |
| Modelo canônico Ladder | inteiro | `plcopen/canonical_model.py: SCHEMA_VERSION` |
| Mapa estrutural PLCopen | inteiro | `plcopen/structure_map.py: STRUCTURE_MAP_SCHEMA_VERSION` |
| Análise offline do export | inteiro | `automation/plcopen_export_analysis.py: ANALYSIS_SCHEMA_VERSION` |
| Revisão host-side | inteiro | `automation/host_validation_revision.py: REVISION_SCHEMA_VERSION` |
| Reclassificação de probe | inteiro | `discovery/ladder_probe_reclassify.py: RECLASSIFY_SCHEMA_VERSION` |
| Probe / export IronPython | **string** `"1.0"` | formalizada nos cinco JSON Schemas |
| Dump de API do ScriptEngine | **string** `"2.0"` | contrato próprio, preservado |

Regras que valem:

- cada família **escreve** o seu formato canônico;
- cada leitor **aceita apenas** as versões declaradas pelo seu contrato. Não
  existe aceitação global de `1`/`"1"`/`"1.0"` — isso ligaria silenciosamente
  artefatos incompatíveis. Só um leitor que realmente precise consumir legado
  faz compatibilidade explícita, e registra qual forma recebeu;
- **não existe constante global** de versão. As famílias coincidem no valor
  hoje; precisam poder divergir amanhã sem uma arrastar a outra;
- artefatos já arquivados não são reescritos.

`tests/unit/test_schema_version_families.py` protege exatamente isso: que cada
constante exista e seja própria, que não sobre literal solto na família
inteira, que nenhuma constante global apareça, que os JSON Schemas continuem
`string`, que o `"2.0"` permaneça, e que o modelo canônico **rejeite** receber
`"1.0"` em vez de adaptar-se a ele.

### Como era antes desta normalização

Três padrões convivendo no repositório:

| Padrão | Onde |
|---|---|
| `"schema_version": "1.0"` (**string**) | `analysis/call_graph.py`, `analysis/variable_usage.py`, `cli.py:125`, `diff/project_diff.py`, `export/indexer.py` |
| `SCHEMA_VERSION = 1` (**int**, constante) | `automation/config_models.py`, `indexer/query_response.py`, `plcopen/canonical_model.py` |
| `"schema_version": 1` (**int literal solto**) | `plcopen/structure_map.py`, `automation/host_validation_revision.py`, `automation/plcopen_export_analysis.py`, `discovery/ladder_probe_reclassify.py` |

Um consumidor que compare `schema_version` sem saber o tipo compara `"1.0"`
com `1` e conclui incompatibilidade onde não há — ou pior, o inverso.
`api.py` já mantém `SUPPORTED_INDEX_SCHEMA_VERSIONS = {1}` como conjunto de
inteiros, o que torna a variante string incompatível com a checagem existente.

**Contrato proposto:** `schema_version` é **inteiro**, declarado como
constante `SCHEMA_VERSION` no módulo que define o artefato, nunca literal
solto no ponto de serialização. Artefatos de famílias distintas versionam de
forma independente — não existe versão global do projeto.

*(A proposta original desta seção era "`schema_version` é sempre inteiro". O
inventário completo mostrou que ela valia só para uma das duas famílias — ver
o início da seção.)*

## 8. Campos comuns entre read-only e exportação controlada

Consolidando os eixos acima, o que é comprovadamente comum:

| Eixo | Comum? | Observação |
|---|---|---|
| Procedência (`runtime` + `check_provenance`) | **sim** | já centralizado, não mexer |
| Identidade (quatro `expected_*` + abort) | **sim na validação** | arquivamento diverge — corrigir |
| Safety declaration | **mecanismo sim, chaves não** | duas classes, ambas necessárias |
| `checksums.sha256`, `diagnostics.json`, `report.md`, `safety-declaration.json` | **sim** | o núcleo real |
| Estado terminal | **sim** | fonte única já existe |
| Estado interno | **deveria** | hoje espalhado |
| Resultado científico | **forma sim, vocabulário não** | taxonomia é por canal |
| Descritor da operação | **não** | `manifest` ≠ `invocation` por motivo real |

## Ordem recomendada para a frente 1

1. ~~Corrigir a lacuna de `target-identity.json` na exportação (seção 4).~~
   **Feito** — pendente de smoke supervisionado dentro do MasterTool, já que o
   código alterado roda lá e não pode ser executado sem supervisão visual.
2. ~~Normalizar `schema_version` (seção 7).~~ **Feito** — por família, não
   globalmente; a família de probe/export segue em string por contrato.
3. ~~Dar fonte única aos estados internos (seção 2).~~ **Feito.**
4. ~~Extrair a operação supervisionada comum.~~ **Feito**, limitada ao núcleo de
   quatro artefatos, ao mecanismo de safety declaration com classe explícita,
   à procedência e à identidade.

O que **não** deve ser abstraído: os artefatos exclusivos de cada canal, o
vocabulário de veredito científico, a distinção `manifest`/`invocation`, e a
exclusão mútua literal entre operações — que `docs/16` mantém não-abstraída de
propósito, por ser mais auditável nesta fase.

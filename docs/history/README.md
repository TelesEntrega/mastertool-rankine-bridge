# Classificação documental — o que cada documento é

> Este diretório **não contém cópias**. Ele contém a classificação. Os
> documentos numerados continuam em `docs/`, com os caminhos que sempre
> tiveram, porque esses caminhos estão citados em mensagens de commit, em
> relatórios de execução e nos artefatos de run — mover os arquivos quebraria a
> cadeia de evidência para ganhar arrumação.
>
> Estado corrente: [`../CURRENT_STATUS.md`](../CURRENT_STATUS.md).
> Plano corrente: [`../ROADMAP.md`](../ROADMAP.md).

## As quatro classes

| Classe | Significado | Pode ser editado? |
|---|---|---|
| `NORMATIVO` | contrato ou especificação ainda vigente | sim, por slice próprio |
| `EVIDÊNCIA` | relatório de uma execução real, datado | **NUNCA** — é registro, não documentação |
| `PONTEIRO` | descrevia o estado; agora aponta para a fonte canônica | sim, para apontar |
| `HISTÓRICO` | superado; preservado com cabeçalho que diz o que mudou | só o cabeçalho |

**A regra que governa tudo:** um relatório de execução nunca é corrigido. Se
ele afirma algo que depois se mostrou incompleto, quem corrige é o documento
seguinte — e a contradição entre os dois é informação, não defeito. Reescrever
evidência para "manter a documentação em dia" destruiria a única coisa que
distingue este projeto de um projeto que declara resultados.

## Classificação

### Fonte canônica

| Documento | Classe |
|---|---|
| [`CURRENT_STATUS.md`](../CURRENT_STATUS.md) | **fonte única do estado vigente** |
| [`ROADMAP.md`](../ROADMAP.md) | `NORMATIVO` — plano corrente |
| [`CAPABILITY_MATRIX.md`](../CAPABILITY_MATRIX.md) | `NORMATIVO` — o que está provado, e em que grau |
| [`COMPATIBILITY_MATRIX.md`](../COMPATIBILITY_MATRIX.md) | `NORMATIVO` — produto, versão, template |
| [`SAFETY_MODEL.md`](../SAFETY_MODEL.md) | `NORMATIVO` — modelo de segurança consolidado |
| [`PENDENCIAS.md`](../PENDENCIAS.md) | `NORMATIVO` — registro de lacunas de R0 a R12, datado de 2026-08-01. É levantamento, não plano: não decide ordem de execução, e cada item fecha por slice próprio, com a evidência que o derruba |
| [`FIELD_QUALIFICATION.md`](../FIELD_QUALIFICATION.md) | `NORMATIVO` — os 38 itens que só fecham com o MasterTool aberto, cada um ligado ao marco que depende dele. Derivado de `PENDENCIAS.md`; não é evidência de execução, é a fila do que medir |
| [`COVERAGE_BASELINE.md`](../COVERAGE_BASELINE.md) | `NORMATIVO` — a cobertura medida em 2026-08-01, com o escopo declarado e **sem meta imposta**. Fotografia datada: a régua é o comando, e refazer a medição substitui a página |

### Contratos e especificações vigentes

| Documento | Classe | Observação |
|---|---|---|
| `01-architecture.md` | `NORMATIVO` | |
| `02-mastertool-setup.md` | `NORMATIVO` | específico do IEC XE 3.63 |
| `04-export-format.md` | `NORMATIVO` | |
| `05-analysis-pipeline.md` | `NORMATIVO` | |
| `08-safety.md` | `NORMATIVO` | consolidado em `SAFETY_MODEL.md`; o YAML continua prevalecendo |
| `09-troubleshooting.md` | `NORMATIVO` | |
| `11-read-only-project-scanner.md` | `NORMATIVO` | |
| `12-read-only-text-export.md` | `NORMATIVO` | |
| `13-static-project-indexer.md` | `NORMATIVO` | |
| `16-supervised-runner-contract.md` | `NORMATIVO` | |
| `17-plcopen-ladder-schema.md` | `NORMATIVO` | schema observado no 3.63 |
| `19-contratos-de-execucao.md` | `NORMATIVO` | |
| `20-contrato-topologia-logica.md` | `NORMATIVO` | |
| `21-contrato-semantica-ladder.md` | `NORMATIVO` | contrato da L5, **implementação nunca começou** — vira a fase R4 |
| `28-contrato-escrita-controlada-mastertool-x.md` | `NORMATIVO` | contrato vigente da escrita |
| `35-contrato-pacote-iec-minimo.md` | `NORMATIVO` | |
| `38-contrato-task-e-program-call.md` | `NORMATIVO` | |
| `29`, `30`, `31`, `32` | `NORMATIVO` | planos de fase; cumpridos, mantidos como especificação do que foi executado |

### Evidência — imutável

Relatórios de execução e de medição. Cada um registra o que foi observado numa
data, com run citada. **Nenhum destes é editado.**

| Documento | O que registra |
|---|---|
| `03-scripting-discovery.md` | descoberta do scripting no 3.63 |
| `15-automation-launcher-roadmap.md` | medições do launcher no MT8500 3.63 |
| `22-varredura-completa-da-arvore.md` | varredura completa da árvore |
| `23-export-por-dispositivo.md` | export PLCopen dispositivo a dispositivo |
| `24-investigacao-api-de-parametros.md` | caminho descartado **com evidência** |
| `25-inventario-de-comunicacao.md` | inventário determinístico offline |
| `26-compatibilidade-de-export-por-dispositivo.md` | 3.63 × 3.70; **não se estende ao MasterTool X** |
| `27-reconhecimento-mastertool-x.md` | W0 — reconhecimento do MT9000 |
| `33`, `34` | W1.3A e W1.3B — edição textual |
| `36-qualificacao-template-tmf-v1.md` | qualificação read-only do template |
| `37` | W1.4 — autoria integrada com build |
| `39` | W2 — program call |
| `40` | determinismo de W1.4, cinco gerações |
| `41` | W3 — a chamada idiomática |
| `42` | W4 — a fábrica de projetos |
| `43` | W5 — FB e FUNCTION em cadeia |
| `44` | determinismo da fábrica |
| `45` | `DutType` e `KindOfTask` — alcance |
| `46` | W6 — DUT provado, `create_task` recusado **naquele momento** |
| `47` | W7 — fábrica completa |
| `48` | W8 — task com POU |
| `49` | W9 — tempo da task, primeira escrita de propriedade |
| `51-qualificacao-r1-task-n10.md` | **R1 — qualificação das operações de task, N=10.** Fecha as três que o `50` deixou: com ela, as CATORZE do contrato estão `repeatable` |
| `50-qualificacao-r1-n10.md` | **R1 — qualificação N=10.** Promove ONZE operações para `repeatable`, e diz no próprio documento quais três NÃO promove e por quê |
| `52-prova-w10-alteracao-transacional.md` | **W10 — alteração de objeto PREEXISTENTE.** Primeira escrita provada sobre algo que o plano não criou: hash anterior medido e conferido no campo antes do `replace`, e `only_authorized_changed` na comparação antes×depois |
| `53-qualificacao-w10-n10.md` | **W10 — qualificação N=10.** Promove `replace` sobre alvo PREEXISTENTE para `repeatable`; três das quatro palavras do gate da R2 medidas |
| `54-prova-w10-reversao.md` | **W10-REVERT — reversão medida.** A quarta palavra do gate da R2: alteração desfeita pelo MESMO mecanismo, e o projeto revertido é indistinguível do template original |
| `55-qualificacao-w10-revert-n10.md` | **W10-REVERT — qualificação N=10.** Reversão repetível; achou que a qualificação de template não dizia de qual arquivo falava, e que a obrigatoriedade condicional do pacote não chegava ao selo |
| `56-qualificacao-w10-redo-n10.md` | **W10-REDO — desfazer a reversão, N=10.** O ciclo fecha nas duas direções; e o achado de que *redo* não é operação nova, e sim a alteração sobre outra base |
| `api/mastertool-api-observations.md` | diário de APIs observadas |

> **Sobre o `46`:** ele registra `create_task` como `field_proven: False`, e
> isso estava certo na data. O `48` mostra que o bloqueio era de interpretação —
> o aviso do fabricante nomeia a `MainTask`, ou seja, protege um **objeto**, e
> foi lido como proibindo um **verbo**. Ler o `46` isolado leva a conclusão
> errada sobre o estado de hoje; ler o `46` seguido do `48` é exatamente o
> registro de como o erro foi encontrado. Por isso o `46` não é corrigido.

### Ponteiros

| Documento | Classe | Para onde aponta |
|---|---|---|
| `18-estado-e-proximo-passo.md` | `PONTEIRO` | era o documento canônico de retomada; passa a ser **registro histórico de retomada**. O estado vigente é `CURRENT_STATUS.md`. Nota: a tabela "Marcos" dentro dele ficou desatualizada em relação à tabela do topo do próprio arquivo — as duas divergem sobre W1.3/W1.4/W2 |
| `INDEX.md` | `PONTEIRO` | índice geral |
| `PROJECT_CONTEXT_AND_ROADMAP.md` | `PONTEIRO` | checkpoint narrativo; enquadra o "estado atual" em torno de leitura somente, anterior a W1–W9 |
| `api/scriptengine-capabilities.md` | `PONTEIRO` | mapa de capacidades; `CAPABILITY_MATRIX.md` é a fonte |
| `api/compatibility-matrix.md` | `PONTEIRO` | `COMPATIBILITY_MATRIX.md` é a fonte |

### Histórico — superado, com cabeçalho

| Documento | O que ficou errado |
|---|---|
| `00-overview.md` | tabela de fases diz que compilação não foi implementada e importação está bloqueada |
| `06-compilation.md` | "Fase 3 — não implementada"; o `build` é executado desde W1.4 |
| `07-controlled-import.md` | descreve a importação no 3.63, que segue desabilitada — **não** descreve a autoria no MasterTool X, que é outro mecanismo |
| `10-roadmap.md` | substituído por `ROADMAP.md` |
| `14-ladder-roadmap.md` | medições continuam válidas; o planejamento foi substituído |

### Relatórios de entrega na raiz do repositório

`RELATORIO-BASELINE-v0.2.0-ladder-structure.md`, `RELATORIO-ENTREGA-01.md`,
`RELATORIO-VALIDACAO-OPERACIONAL-2026-07-24.md` e
`RELATORIO-VALIDACAO-v0.1.0.md` são `EVIDÊNCIA`, datados de suas entregas, e
não são editados.

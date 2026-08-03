# Execução R1 — qualificação das operações de task, N = 10

> Registro de execução. Lote `R1-TASK-N10`, dez execuções independentes em
> 2026-08-02, sobre a segunda spec canônica. **Documento de evidência: não é
> corrigido depois.**

## O que este lote fecha

`docs/50` promoveu onze operações e disse, no próprio texto, quais três não
promovia: `create_task`, `bind_program_to_task` e `configure_task` — porque
aquela spec reusa a `MainTask` e não as toca. Este lote usa uma spec que
**cria** task, e fecha exatamente essas três.

Com ele, **as catorze operações do `EXECUTOR_CONTRACT` estão `repeatable`**.

```text
10 runs solicitadas       10 iniciadas        10 concluídas
10 plan_executed          13 passos executados, 3 delegados, de 16 (em todas)
10 build_verified         0 erros, 0 avisos, 0 mensagens não classificadas
10 factory_output_verified
10/10 equivalentes        independência limpa nos 45 pares
saída inalterada pelo build nas dez (`output_unchanged_by_build`)
```

## Entradas, congeladas por hash

| O quê | Valor |
|---|---|
| Spec | `C:\mastertool-x-r1\specs\w9-task-timing-v1.json` |
| Spec sha256 | `c369c2f2873048e5b3e005caadf0bcc163b434c77196e34f9dd78a8fb43952f4` |
| Origem | cópia byte a byte da spec da `run-037` (`docs/49`) — recuperada, não reconstruída |
| Template | `TemplateExemplo v1.project`, sha256 `596625796e4e…815f5` |
| Fase de autoria | `W9_PROVE_TASK_TIMING` |
| Fase de build | `W9_VERIFY_BUILD` |
| Lote | `C:\mastertool-x-r1\qualificacao-task-n10` |

<caption>

**Como ler:** a fase de autoria é a que autoriza `create_task`, `add` e as
quatro escritas de propriedade. Ela já existia e já tinha sido exercida uma vez
(`docs/49`); este lote a reabriu com a **mesma** allowlist para medir repetição.

</caption>

## O que a spec cria, em cada uma das dez runs

```text
GVL_W8            GVL
PRG_CICLO         PROGRAM, chamado pela MainTask (existente, reusada)
PRG_DIAG          PROGRAM, chamado pela task criada
TaskDiagnostico   task NOVA: Cyclic, t#500ms, prioridade 25
```

As quatro escritas de propriedade — `kind_of_task`, `interval`,
`interval_unit`, `priority` — acontecem sobre a task criada, e são relidas
depois de escritas: atribuição que não pega é o modo de falha próprio desta
classe, porque um campo não levanta ao falhar, apenas continua com o valor
antigo.

## Um número que merece explicação

`objects_verified = 3` na verificação, com **quatro** objetos criados. Não é
divergência: a verificação compara **filhos diretos** do container
(`LIMIT_DIRECT_CHILDREN_ONLY`), e a task de configuração não é filha direta
dele. O limite está declarado em `CAPABILITY_MATRIX.md` desde a W1.4 e não
mudou aqui — quem quiser o quarto objeto na contagem precisa de uma varredura
que ninguém escreveu ainda.

## O que este lote NÃO estabelece

- **Não promove `template_qualified`.** As duas lacunas do perfil seguem
  abertas: inventário de dispositivos e library lock.
- **Não amplia o vocabulário de task.** `event`, `external_event`,
  `core_binding`, `parent_synchron_task` e `watchdog.*` continuam fora — sem
  receptor nem verificação escritos. `Cyclic` é o único `KindOfTask` exercido.
- **Não prova edição de task preexistente.** A task deste lote é criada pela
  própria spec; `bind_program_to_task` só serve para essa.
- **Não diz que o CLP executa.** O `.project` declara `t#500ms`; ninguém mediu
  ciclo, e isso segue fora do escopo.

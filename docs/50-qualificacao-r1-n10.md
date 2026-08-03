# Execução R1 — qualificação de repetibilidade, N = 10

> Registro de execução. Lote `R1-N10`, dez execuções independentes da mesma
> especificação sobre o mesmo template, em 2026-08-02. **Documento de
> evidência: não é corrigido depois.**

## O que este lote estabelece

Dez execuções independentes da fábrica produziram projetos **equivalentes entre
si e independentes**, todos compilados e verificados. É a primeira evidência do
projeto capaz de promover capacidade acima de `field_proven`, e promove
**onze** operações — não as catorze.

```text
10 runs solicitadas       10 iniciadas        10 concluídas
10 plan_executed          21 passos executados, 3 delegados, de 24 (em todas)
10 build_verified         0 avisos do fabricante
10 factory_output_verified
10/10 equivalentes à referência
independência limpa nos 45 pares
```

## Entradas, congeladas por hash

| O quê | Valor |
|---|---|
| Spec | `C:\mastertool-x-r1\specs\w7-factory-full-v1.json` |
| Spec sha256 | `2e382c763ce4796a99f44cdf58ae5f18003c8a4f44d3fdc174e1f37a08db1481` |
| Origem da spec | cópia byte a byte de `spec-maquina.json`, a spec das runs 034/035 (`docs/47`) |
| Template | `TemplateExemplo v1.project`, sha256 `596625796e4efd54d3cc2d6286e858b683f0f58de66ab9a36eed532dd1d815f5` |
| Perfil | `mastertool-x-4.1.0.11-tmf-v1-io-v1` |
| Produto | MasterTool X `4.1.0.11`, caminho **explícito** |
| Lote | `C:\mastertool-x-r1\qualificacao-n10` |

<caption>

**Como ler:** a spec não foi reconstruída a partir do plano — os bytes exatos
foram recuperados e conferidos. Nenhuma destas entradas mudou entre o primeiro
preflight e o fechamento do último gate.

</caption>

## Método — dois estágios, dois gates, quatro commits

`-ExecutePlan` e `-ExecuteBuild` são modos mutuamente exclusivos da fábrica e
rodam sob fases diferentes. Não existe uma passada só.

```text
preflight (plan)  → gate W7_FACTORY_FULL aberto   → 10 planos → gate fechado
preflight (build) → gate W7_VERIFY_BUILD aberto   → 10 builds → gate fechado
```

Cada abertura e cada fechamento em **commit isolado**, sem implementação junto.
O gate nunca ficou aberto entre estágios.

## As onze operações promovidas

| Operação | Onde foi exercida |
|---|---|
| `create_gvl`, `create_program`, `create_function`, `create_function_block`, `create_dut` | executor (probe 46), sob `W7_FACTORY_FULL` |
| `create_program_call` | executor, `composed_at_runtime` sobre a `UserPrg`, com hash antes e depois |
| `replace` | executor, 11 passos por run |
| `save_as` | executor |
| `reopen`, `build`, `verify` | estágio de build (probes 40 e 47), sob `W7_VERIFY_BUILD` |

<caption>

**Como ler:** "exercida" significa que o passo executou nas dez runs, com
artefato citável. Um passo delegado pelo executor não é um passo que não
aconteceu — é um passo que aconteceu em outra fase, com abertura própria.

</caption>

## As três que NÃO foram promovidas

`create_task`, `bind_program_to_task` e `configure_task` continuam
`field_proven`. **A spec deste lote reusa a `MainTask` e não as toca.**
Promovê-las junto seria creditar o que ninguém mediu — e é exatamente o erro
que a escala de maturidade existe para impedir.

## Campos voláteis, exibidos

| Campo | Valores distintos em 10 execuções | Leitura |
|---|---:|---|
| `generated_at` | 10 | varia a cada execução, como esperado |
| `output_project_path` | 10 | idem — cada run tem saída própria |
| `plan_sha256` | 1 | constante: mesma spec, mesmo plano |

<caption>

**Como ler:** estes campos não reprovam o lote — estão numa allowlist literal,
campo a campo. A tabela existe porque a allowlist decide o veredito, não a
visibilidade.

</caption>

## O que este lote NÃO estabelece

- **Não promove `template_qualified`.** O perfil ainda tem duas lacunas
  abertas: inventário de dispositivos e library lock. São perguntas sobre o
  template, e este lote respondeu uma pergunta sobre repetição.
- **Não promove as três operações de task.** Ver acima.
- **Não diz nada sobre outra instalação, outra máquina ou outra versão.** O
  produto foi `4.1.0.11`, num caminho explícito porque há **onze** instalações
  Altus nesta máquina e a busca automática recusa, corretamente.
- **Não diz que o CLP executa.** Nada aqui mede ciclo ou comportamento em
  runtime, e isso continua fora do escopo do produto.

## Defeitos que o piloto N=3 achou antes deste lote

Registrados porque explicam por que o piloto existiu:

1. o seletor semântico lia o nome da **raiz**, e `ScriptProject` não expõe
   `get_name` — recusa nas três runs, sem escrever nada;
2. `container_selection` não era persistido: a recusa nomeava a causa e o
   artefato não dizia qual nó;
3. `-BuildPlan` recebia o plano de autoria, e o probe 40 espera outro
   documento.

Os três teriam custado dez execuções cada, em vez de três.

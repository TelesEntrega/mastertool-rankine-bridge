# Baseline de cobertura — medida, sem meta imposta

> **O que este documento é.** A fase P0.2 instalou a medição e mediu. Os
> 90% que apareciam no roadmap eram **proposta de gate futuro**, não
> requisito vigente e não métrica avaliada: antes desta medição não havia
> `pytest-cov` no ambiente nem configuração de cobertura no `pyproject`, e
> portanto não havia base para afirmar cobertura alguma. Nenhum limiar é
> imposto aqui — escolher meta antes de conhecer o número seria escolher
> pela expectativa.

| | |
|---|---|
| Medido em | 2026-08-01 |
| Comando | `pytest --cov=mastertool_bridge --cov-branch` |
| Escopo | `src/mastertool_bridge/` — **só a biblioteca CPython 3** |
| Statements | 9313 |
| Não cobertos | 1060 |
| Ramos | 3420 |
| Ramos parciais | 487 |
| **Cobertura (linha + ramo)** | **86%** |
| Suíte | 3919 passed, 1 skipped |

## 1. Por que o escopo não inclui `scripts/`

`scripts/mastertool/` roda em **IronPython 2.7 dentro do MasterTool**.
Vários desses módulos são importados pelos testes via `importlib` para
verificação estática — AST, vocabulário fechado, precondição —, o que
produziria um número de cobertura para linhas que **nunca executam fora do
produto**. Um percentual global misturando as duas camadas descreveria mal
as duas: inflaria a da biblioteca e daria falsa garantia sobre a dos probes.

São três regimes de verificação, e cada um mede o que consegue:

| Camada | Como é verificada hoje | Cobertura de linha faz sentido? |
|---|---|---|
| `src/mastertool_bridge/` (CPython 3) | testes unitários e de integração | sim — é o número desta página |
| `scripts/mastertool/` (IronPython 2.7) | AST, dublês de API, vocabulário fechado, execução de campo | não isoladamente: a linha só executa dentro do produto |
| Contratos com o produto | evidência de run, documento numerado | não — é qualificação, não cobertura |

<caption>

**Como ler:** a coluna da direita não diz que a camada é menos verificada —
diz que a régua é outra. Somar as três num percentual único produziria um
número que ninguém poderia usar para decidir nada.

</caption>

## 2. Cobertura por subsistema

| Subsistema | Arquivos | Statements | Cobertura |
|---|---:|---:|---:|
| `indexer` | 17 | 2774 | 83% |
| `automation` | 12 | 1599 | 86% |
| `plcopen` | 5 | 1198 | 93% |
| `templates` | 3 | 865 | 86% |
| `(raiz)` | 9 | 624 | 76% |
| `planner` | 2 | 438 | 91% |
| `spec` | 1 | 326 | 89% |
| `analysis` | 10 | 255 | 85% |
| `inventory` | 2 | 209 | 97% |
| `audit` | 3 | 190 | 92% |
| `models` | 8 | 156 | 97% |
| `discovery` | 3 | 150 | 91% |
| `static_api` | 3 | 144 | 97% |
| `export` | 5 | 132 | 77% |
| `utils` | 7 | 119 | 87% |
| `changes` | 5 | 46 | 67% |
| `docs` | 5 | 46 | 77% |
| `diff` | 4 | 42 | 85% |

<caption>

**Como ler:** a porcentagem é linha + ramo, o mesmo critério do total. Um
subsistema pequeno com número baixo pesa pouco no total e pode ainda assim
ser o mais crítico — a tabela seguinte é a que serve para decidir.

</caption>

## 3. Os arquivos com menor cobertura

| Arquivo | Statements | Cobertura | Leitura |
|---|---:|---:|---|
| `config.py` | 33 | 0% | nenhuma linha executada pela suíte |
| `utils/paths.py` | 14 | 0% | nenhuma linha executada pela suíte |
| `analysis/variable_usage.py` | 6 | 0% | nenhuma linha executada pela suíte |
| `changes/approval.py` | 6 | 0% | nenhuma linha executada pela suíte |
| `indexer/__main__.py` | 5 | 0% | nenhuma linha executada pela suíte |
| `analysis/complexity.py` | 4 | 0% | nenhuma linha executada pela suíte |
| `analysis/duplicate_code.py` | 4 | 0% | nenhuma linha executada pela suíte |
| `analysis/state_machine.py` | 4 | 0% | nenhuma linha executada pela suíte |
| `changes/package_builder.py` | 4 | 0% | nenhuma linha executada pela suíte |
| `diff/semantic_diff.py` | 4 | 0% | nenhuma linha executada pela suíte |
| `docs/diagram_generator.py` | 4 | 0% | nenhuma linha executada pela suíte |
| `docs/pou_documenter.py` | 4 | 0% | nenhuma linha executada pela suíte |
| `__main__.py` | 3 | 0% | nenhuma linha executada pela suíte |
| `export/normalizer.py` | 24 | 41% | caminhos principais sem exercício |
| `logging_config.py` | 24 | 62% | ramos de erro/recusa parcialmente exercitados |

<caption>

**Como ler:** cobertura baixa aqui é *achado a investigar*, não defeito
provado. Um módulo com 0% pode ser código morto (e aí a correção é removê-lo),
caminho só exercido em campo (e aí a régua é outra) ou lacuna real de teste.
Distinguir os três casos é o próximo passo, e não foi feito nesta medição.

</caption>

## 4. O que esta medição NÃO autoriza concluir

- **Não autoriza dizer que a biblioteca está 86% testada.** Cobertura mede
  linha executada, não asserção feita: um teste que importa um módulo e não
  afirma nada cobre 100% dele.
- **Não autoriza comparar com os 90% do roadmap.** Aquele número era proposta
  para camadas específicas (planner, gate, schemas, diff, changes), não para o
  total, e nunca foi aceito como requisito.
- **Não autoriza gate na CI ainda.** `fail_under` fica deliberadamente ausente
  do `pyproject`: limiar imposto antes de classificar os módulos de 0% viraria
  pressão para escrever teste que cobre linha sem verificar comportamento.

## 5. Limites

O relatório JSON completo **não é versionado**: muda a cada execução e viraria
ruído de diff. Reproduzir é uma linha, e o comando está no quadro acima. Esta
página é a fotografia datada; a régua é o comando.

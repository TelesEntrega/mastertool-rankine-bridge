# Relatório da baseline — v0.2.0-ladder-structure

Data: 2026-07-29 · Commit: `e43a198` · Baseline anterior: `v0.1.0` (`8eddcb7`)

Fecha a estrutura Ladder: a lógica gráfica de uma POU real sai do MasterTool
por um caminho controlado, é interpretada num modelo canônico versionado, e o
mecanismo que produz os artefatos foi consolidado antes de qualquer camada
nova. **Nenhuma semântica Ladder entrou** — isso é a próxima fase, não esta.

## 1. Estado em uma linha

```text
export_xml controlado → PLCopen XML tc6_0200 → mapa estrutural
    → modelo canônico → parser → JSON canônico da POU real
```

Validado de ponta a ponta em execução supervisionada real no dia da baseline.

## 2. Números

| | |
|---|---|
| Suíte (local, sem `test_mcp_server_e2e.py`) | **1264 passed, 1 skipped** |
| Suíte (clone limpo, ambas as configurações) | **1263 passed, 2 skipped** |
| `validate-repository.py` | `[OK]` local e nos dois clones |
| Commits desde `v0.1.0` | 48 |
| Arquivos versionados | 333 |
| Smoke supervisionado | run `2026-07-29_09-27-27` — 46 checagens, 0 falhas |

A diferença de um teste entre local e clone é o export real: presente aqui,
ausente no clone, onde **pula com motivo explícito** em vez de sumir da
contagem.

## 3. A POU real, interpretada

Números do parser sobre o XML exportado no smoke desta baseline:

| | |
|---|---|
| elementos | 42 — **nenhum `unknown`** |
| pinos | 40 |
| evidência de conexão | 32 = 29 `plcopen_connection` + 3 `vendor_parallel_branch` |
| arestas derivadas | 32 |
| redes | **4, todas `confirmed_by_marker_and_connectivity`** |
| fronteiras de rede | 5 (uma vazia, registrada e não convertida em rede) |
| componentes | 14 |
| extensões do fornecedor | 6 |
| elementos não atribuídos | 8 (prólogo, trilhos, marcadores) |

Taxonomia: 14 `in_variable`, 10 `block`, 6 `vendor_element`, 5 `comment`,
3 `coil`, 2 `contact`, 2 trilhos.

As quatro redes são confirmadas por **dois sinais independentes** — marcador
`networktitle` do fornecedor e conectividade topológica sem trilhos, incluindo
as arestas de `ParallelBranch`. Os dois concordam.

## 4. Critérios da tag

| Critério | Estado |
|---|---|
| PLCopen exportado de forma controlada | ✅ uma única chamada `export_xml`, escopo autorizado |
| XML real validado | ✅ `P1_graphical_body_present` |
| Schema mapeado | ✅ `docs/17-plcopen-ladder-schema.md` |
| Modelo canônico versionado | ✅ `plcopen/canonical_model.py`, `SCHEMA_VERSION = 1` |
| POU real carregada sem elementos desconhecidos | ✅ 42 elementos, 0 `unknown` |
| Redes por dois sinais independentes | ✅ 4/4 confirmadas |
| Estados e schemas consolidados | ✅ `docs/19-contratos-de-execucao.md` |
| `target-identity` validado em runtime | ✅ smoke de 2026-07-29 |
| Núcleo comum revisado | ✅ `common/artifacts.py`, artefatos byte a byte idênticos |
| Suíte e clone limpo aprovados | ✅ nas duas configurações de `core.autocrlf` |

## 5. Smoke supervisionado — run `2026-07-29_09-27-27`

Execução real, UI visível, sobre cópia descartável do projeto.

- `final_state` `completed`, saída 0, 94 s
- hash do projeto **inalterado** antes e depois
- projeto **original não tocado**, não salvo, sem build/online/download/force
- procedência confirmada: IronPython 2.7.12, plataforma `cli`
- nenhum processo órfão
- `artifact_validation.ok = true`, **sem erros e sem warnings**
- `target-identity.json` presente em `checked_files`, coberto e conferido no
  `checksums.sha256`
- safety declaration da exportação: `export_xml_called` verdadeiro,
  `export_xml_call_count = 1`, escopo `authorized_disposable_export_root`,
  seis chaves proibidas falsas, sem a chave genérica `write_called`
- índice regenerado: 60 símbolos, 8 tipos, 522 entradas de leitura/escrita

A validação host-side rodou em **modo estrito** (run nova). O modo de revisão
histórica não foi necessário — o que confirma que o contrato atual é cumprido
por uma execução feita hoje, não apenas tolerado em runs antigas.

## 6. O que a consolidação corrigiu

Defeitos reais encontrados **e corrigidos** neste ciclo. A maioria foi exposta
por verificação adversarial ou por execução real, não por revisão de código.

| Commit | Defeito |
|---|---|
| `1140784` | taxonomia confundia acesso por nome com enumeração |
| `d418885` | seção `runtime` nunca emitida — **toda** run supervisionada terminava `failed` |
| `1b650c3` | host pré-criava `export-root`, colidindo com a guarda de output vazio |
| `a294edc` | análise offline lia `export_xml_called` do arquivo errado e pulava sempre |
| `69cdfac` | `formalParameter` das arestas de `ParallelBranch` descartado na travessia evidência → aresta |
| `223a9e5` | exportação validava identidade do alvo mas não a arquivava |
| `f130e5b` | hashes de fixture calculados sobre working tree híbrido LF/CRLF |
| `b190d1b` | `validate-repository.py` exigia diretórios nunca versionados |

Dois padrões se repetiram e valem registro:

**Skip que esconde verificação não executada.** `a294edc` e depois o teste do
export real: um `pytest.skip` de aparência benigna significava que a checagem
nunca rodava. O segundo caso foi pego porque o relatório dizia "export real não
disponível" sobre um arquivo que existia.

**Defeito que só aparece comparando duas fontes.** O `ENO` do `ParallelBranch`
produzia `ambiguous` na fixture — plausível — e escondia que o arquivo real
tinha informação suficiente para resolver. Três defeitos do mapeador de
estrutura apareceram do mesmo jeito. E os dois defeitos de `f130e5b`/`b190d1b`
só existiam fora da máquina de origem: a suíte e o validador passavam aqui e
falhavam em qualquer clone.

## 7. Limites — o que esta baseline NÃO cobre

- **Semântica Ladder não existe.** O modelo descreve estrutura: elementos,
  pinos, evidência de conexão, arestas, redes. Não diz o que a lógica faz.
  Contatos, bobinas, chamadas de bloco e read/write são a próxima fase.
- **Uma POU observada.** O schema foi mapeado a partir de um `functionBlock`
  real. `outVariable`, `inOutVariable`, `connector`, `continuation`, `jump`,
  `label` e `return` estão modelados mas **nunca foram observados** — e o
  modelo distingue `not_observed` de `unsupported` de propósito.
- **`mode="sce"` do `ParallelBranch`** permanece não interpretado.
- **A escrita dos artefatos não é atômica, apesar do nome das funções.**
  `write_json_atomic`/`write_text_atomic` fazem `tmp → remove → rename`.
  IronPython 2.7 não tem `os.replace` (Python 3.3+) e no Windows `os.rename`
  falha se o destino existir, então o passo intermediário é obrigatório — e é
  ele que abre uma janela em que o destino não existe. O que o mecanismo
  garante é mais estreito: o destino **nunca fica com conteúdo pela metade**, e
  o temporário é removido em qualquer falha. O smoke confirmou o comportamento
  observável (artefatos íntegros, nenhum `.tmp` órfão, checksums conferindo),
  o que **não** é o mesmo que provar atomicidade: essa só falharia num crash
  dentro da janela. A mitigação para esse caso continua sendo o
  `status-history.jsonl` append-only, como `docs/16` já estabelecia.
- **A produção do XML é do MasterTool, não do bridge.** `export_xml` escreve
  no `export-root` por conta própria; o bridge observa o diretório antes e
  depois e registra o que apareceu (`filesystem-before/after.json`,
  `created-artifacts.json`), mas não tem visibilidade nem controle sobre como
  aquela escrita acontece. Nenhuma garantia de atomicidade é oferecida ou
  presumida ali.
- **7 testes async falham por ambiente** — `pytest-asyncio` não está instalado
  no venv. Preexistente, fora do escopo da consolidação por decisão explícita,
  e por isso a suíte é reportada ignorando `test_mcp_server_e2e.py`.
- **Sem lint mecânico**: `ruff` também não está no venv.
- **Nada é executado dentro do MasterTool sem supervisão humana.** Não é
  cadência, é limite estrutural.

## 8. Reprodução

```powershell
git clone -c core.longpaths=true <repo> mastertool-rankine-bridge-clean
cd mastertool-rankine-bridge-clean
python -m pytest -q --ignore=tests/test_mcp_server_e2e.py
python scripts/maintenance/validate-repository.py
```

`core.longpaths=true` é necessário: há caminhos de fixture que estouram o
MAX_PATH do Windows.

Esperado: `1263 passed, 2 skipped` e `[OK] Repositório consistente`, idêntico
com `core.autocrlf` em `true` ou `false`.

## 9. Depois desta baseline

```text
topologia lógica → semântica de contatos e bobinas → chamadas de blocos
→ read/write Ladder → unificação com o índice ST
```

Nada disso deve começar antes de a tag existir.

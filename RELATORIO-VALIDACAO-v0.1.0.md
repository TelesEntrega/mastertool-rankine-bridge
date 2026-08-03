# Relatório de validação — v0.1.0 (StaticProjectIndexer completo)

Data: 2026-07-24 · Tag: `v0.1.0` · Commit: `1213dc2` · Modo: read_only

Gate de estabilização, fechado antes de qualquer novo recurso, cobrindo tudo
que foi construído sobre a exportação textual já validada
(`RELATORIO-ENTREGA-01.md`): parser ST determinístico → resolução de
símbolos → índices JSON estáveis → consultas determinísticas → linguagem
natural controlada → API Python pública → servidor MCP.

## 1. Histórico de commits

16 commits no repositório, em duas fases: os 2 primeiros consolidam a
aquisição estrutural/exportação textual já validadas em runtime real contra
`ExemploPlanta V1.0.project`; os 14 seguintes constroem o StaticProjectIndexer
de ponta a ponta.

| # | Commit | Descrição |
|---|--------|-----------|
| 1 | `14e4bbb` | feat: add validated read-only MasterTool tree and text export |
| 2 | `264aeb1` | docs: add consolidated project context and roadmap checkpoint |
| 3 | `36dda15` | feat: add initial static project indexer |
| 4 | `d686482` | feat: add ST statement and call indexing |
| 5 | `757f711` | fix: preserve dotted names in expression reference scanning |
| 6 | `ecb6212` | feat: add symbol resolution and read-write analysis |
| 7 | `bb4a4b6` | feat: resolve nested GVL instance member references |
| 8 | `2ddc69f` | feat: add deterministic project index queries |
| 9 | `8124ed0` | fix: correct find_calls direction |
| 10 | `50208c4` | feat: add deterministic query intent parsing |
| 11 | `fa11c68` | feat: add grounded natural-language query responses |
| 12 | `977e7fe` | feat: add DUT and STRUCT type indexing |
| 13 | `e44d4a6` | feat: add public Python API for project queries |
| 14 | `523f443` | feat: add MCP server for project index queries |
| 15 | `265d444` | test: add end-to-end MCP client integration test |
| 16 | `1213dc2` | docs: update roadmap and context through MCP server milestone |

Cada um dos commits 3–16 foi verificado **independentemente** antes de
commitar — nunca aceito o autorrelato de um subagente como prova: testes
re-executados, diff real lido linha a linha, e um smoke test próprio
(separado do smoke test do subagente) contra o export real de
`ExemploPlanta V1.0.project` (`workspace/exports/2026-07-23_17-29-54_13_validate_text_exporter/`).

Essa disciplina encontrou **2 bugs reais** que os subagentes que
implementaram as fatias originais não haviam pego:

- **`find_calls` com a direção semântica trocada** (respondia "quem chama
  X" em vez de "o que X chama") — descoberto ao mapear as frases em
  linguagem natural da família "Chamadas realizadas" para o comando
  existente; corrigido em commit isolado (`8124ed0`) antes do commit que
  dependia dele.
- **`load_query_bundle` não recarregando os `TypeSymbol` de STRUCT/DUT do
  disco** — descoberto ao rodar `find_symbol` numa cadeia STRUCT através da
  API Python recém-criada; `resolved-references.json` já estava correto
  (pré-computado), mas a consulta AO VIVO ainda dava `partially_resolved`.
  Corrigido dentro do mesmo commit que expôs o problema (`e44d4a6`).

## 2. Arquitetura entregue

```text
export textual (ReadOnlyTextExporter, já validado)
        ↓
parser ST determinístico (tokenização → statements → declarações,
nunca só regex)
        ↓
resolução de símbolos (7 níveis de prioridade, nunca escolhe candidato
por suposição em ambiguidade) + classificação read/write por regra fixa
        ↓
11 artefatos JSON estáveis em disco (symbols/references/calls/
type-index/read-write-index/...)
        ↓
5 consultas determinísticas sobre os JSONs (find symbol/reads/writes/
calls/callers) — nunca reprocessa ST
        ↓
parser de intenção em linguagem natural controlada (PT/EN, ~28 padrões
fixos, zero IA/fuzzy matching)
        ↓
resposta fundamentada nas evidências (templates fixos, nunca geração
livre)
        ↓
API Python pública, tipada e estável (mastertool_bridge.ProjectIndex)
        ↓
servidor MCP fino (8 tools, sem lógica de domínio própria)
```

Descrição completa de cada camada, modelo de dados e regras de resolução:
`docs/13-static-project-indexer.md`.

### Componentes principais

| Camada | Módulo | Responsabilidade |
|--------|--------|-------------------|
| Léxico | `indexer/st_lexer.py` | Tokenização ST, preserva arquivo/linha/coluna |
| Declarações | `indexer/declaration_parser.py`, `gvl_parser.py`, `dut_parser.py` | POU, GVL, DUT (STRUCT/alias/enum-como-tipo-existente) |
| Statements | `indexer/statement_parser.py` | Atribuições, condicionais, chamadas, cadeias pontuadas com índice |
| Resolução | `indexer/symbol_resolver.py` | 7 níveis de prioridade, cadeias N≥2 segmentos, STRUCT/alias com detecção de ciclo |
| Read/write | `indexer/reference_resolver.py`, `call_resolver.py` | Classificação por regra fixa de contexto+operador |
| Orquestração | `indexer/export_loader.py` | `build_static_index()` — 11 artefatos JSON |
| Consultas | `indexer/query.py` | `find_symbol/reads/writes/calls/callers`, sobre JSON já gerado |
| Intenção NL | `indexer/query_intent.py` | Parser de ~28 padrões fixos PT/EN, zero IA |
| Resposta NL | `indexer/query_response.py` | Templates fixos de resposta fundamentada em evidências |
| API pública | `api.py` | `ProjectIndex`, `QueryResult`, `QueryAnswer`, `QueryIntent`, `QueryEvidence` |
| MCP | `mcp_server.py` | 8 tools finas sobre `ProjectIndex`, dependência nova `mcp` (SDK oficial) |

## 3. Testes

**605 passed, 1 skipped** na suíte completa (`python -m pytest tests/ -v`),
zero falhas, incluindo:

- Testes unitários de cada camada do indexer (lexer, parsers, resolvedor de
  símbolos, classificação read/write) — fixtures sintéticas, nomes
  diferentes dos dados reais do cliente.
- Testes de integração de `query.py`/`query_intent.py`/`query_response.py`.
- Testes da API pública (`tests/test_api.py`) e do servidor MCP
  (`tests/test_mcp_server.py`, chamadas diretas em processo).
- **Teste end-to-end via protocolo MCP real** (`tests/test_mcp_server_e2e.py`):
  sobe o servidor como subprocesso de verdade, conecta como cliente MCP real
  (handshake, `list_tools()`, `call_tool()` com serialização real), não
  apenas chamadas de função em processo.
- `python scripts/maintenance/validate-repository.py` → `[OK] Repositório
  consistente.`

### Amostragem manual (contra o export real, repetida a cada commit)

| Consulta | Resultado |
|----------|-----------|
| `find symbol TripTip` | `ambiguous`, 2 candidatos (`INVERSOR_OMRON`, `TRIP_CAUSE_OMRON`) |
| `find writes TripTip` | `found`, 13 ocorrências |
| `find calls MainPrg` | `resolved`, 3 chamadas (`SpecialVariablesPrg`, `StartPrg`, `UserPrg`) |
| `find callers SpecialVariablesPrg` | `resolved`, 1 chamador (`MainPrg`) |
| `find callers MainPrg` | `resolved`, 0 chamadores (ponto de entrada) |
| `VarMotores.MT01.RetornoDisjuntor` | `resolved` (após DUT/STRUCT; antes `partially_resolved`) |
| `VarTPV.V6.Sensor_Aberta` | `resolved` (após DUT/STRUCT; antes `partially_resolved`) |
| `resolved-references.json` (agregado) | 293→409 resolved, 180→64 partially_resolved, 61 unresolved (estável) |
| `resolved-calls.json` (agregado) | estável em 3 resolved + 9 unresolved = 12, em todos os commits |
| `read-write-index.json` (agregado) | estável em 522 entradas totais, em todos os commits |

## 4. Limitações conhecidas (honestas, não bloqueantes)

- **ENUM/UNION/INTERFACE**: reconhecidos como tipo existente
  (`kind="unknown"`), mas não indexados por membro — cadeias que tentam
  acessar um "membro" ficam `partially_resolved`, nunca escondido nem
  resolvido por suposição. Não bloqueia a integração operacional completa.
- **Métodos de FUNCTION_BLOCK**: o modelo de dados não acessa a árvore de
  métodos de uma instância — chamadas de método nunca são afirmadas como
  `resolved`.
- **Chamadas de biblioteca externa** (`SysTimeCore.SysTimeGetUs`, `CONCAT`,
  etc.): honestamente `unresolved` — sem catálogo de símbolos de biblioteca
  padrão CODESYS.
- **Perguntas compostas, "por quê"/"como funciona", resumo de lógica de
  POU**: fora de escopo (`status="unsupported"`) — camada futura, ainda não
  construída.
- **`UnsupportedSchemaError`**: reservada para uso futuro; nenhum artefato
  JSON hoje carrega marcador de versão de schema para checar de verdade.
- **Validação restrita a um único projeto real** (`ExemploPlanta V1.0.project`,
  captura de 2026-07-23): a cadeia completa MasterTool→export→índice→
  consulta→MCP nunca foi re-executada a partir de uma nova sessão real do
  MasterTool — é exatamente o próximo passo já decidido (seção 6).

## 5. Política de segurança

Inalterada por este trabalho — toda a camada de indexação/consulta/API/MCP
é **somente leitura sobre arquivos já exportados em disco**;
`mastertool_bridge.indexer.*`, `api.py` e `mcp_server.py` nunca importam
nem chamam nada de `scripts/mastertool/` (o único código com acesso real
ao ScriptEngine do MasterTool). Proibições permanentes seguem em
`config/safety-policy.yaml`/`docs/08-safety.md`: nunca alterar o projeto
original, nunca download/online/start-stop/força de variável, nunca
escrita em saída física, nenhuma importação sem backup e aprovação
humana. Nenhuma dessas proibições foi tocada ou relaxada por este marco.

## 6. Como executar

```bash
cd mastertool-rankine-bridge
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements-dev.txt
pip install -e .
pip install mcp            # necessário só para o servidor MCP (dependência nova, ver seção 2)
pytest                      # esperado: 605 passed, 1 skipped
```

**Indexação** (a partir de um export já validado por `ReadOnlyTextExporter`):

```python
from mastertool_bridge.indexer.export_loader import build_static_index
build_static_index("workspace/exports/<run>/", "workspace/analysis/<indice>/")
```

**Consultas via CLI:**

```bash
python -m mastertool_bridge.indexer query symbol Estado_OP --index-dir workspace/analysis/<indice>
python -m mastertool_bridge.indexer ask "onde Estado_OP é escrito?" --index-dir workspace/analysis/<indice> --json
```

**API Python:**

```python
from mastertool_bridge import ProjectIndex
index = ProjectIndex.open("workspace/analysis/<indice>")
print(index.ask("o que MainPrg chama?").to_dict())
```

**Servidor MCP** (stdio — configurar no cliente MCP, ex. Claude Desktop/Code):

```bash
mastertool-bridge-mcp
# ou: python -m mastertool_bridge.mcp_server
```

## 7. Próximo passo

Por decisão explícita do usuário: retomar `scripts/mastertool/00_smoke_test.py`
no MasterTool real, como uma **nova trilha controlada** — validar a cadeia
completa MasterTool → export → índice → consulta → MCP contra uma execução
real, não só contra o export já capturado. Parse de ENUM/UNION/INTERFACE
fica registrado como melhoria de cobertura semântica, explicitamente **não
bloqueante** para essa validação operacional.

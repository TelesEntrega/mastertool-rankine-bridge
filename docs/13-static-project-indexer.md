# StaticProjectIndexer — indexação semântica, consultas determinísticas e ponte MCP

> Estado: **implementado e validado end-to-end** (2026-07-24), em 12 commits
> sequenciais sobre o export textual já validado (`docs/12-read-only-text-export.md`),
> cada um verificado independentemente (testes + leitura do diff real + smoke
> test contra o export real de `ExemploPlanta V1.0.project`) antes de commitar.
> Opera SOMENTE sobre arquivos já exportados em disco — nunca abre o
> MasterTool, nunca reprocessa nada em tempo de consulta que já não tenha
> sido comprovado em tempo de indexação. `tree_walker.py` permanece
> suspenso; este módulo é totalmente independente dele.

## Motivação

O `ReadOnlyTextExporter` (docs/12) produz `declaration.st`/`implementation.st`
por objeto, mas texto bruto não responde perguntas como "onde essa variável é
escrita?" ou "o que essa POU chama?". O `StaticProjectIndexer` é a camada
determinística entre o texto exportado e qualquer consumidor (CLI, script
Python, agente de IA) que precise dessas respostas — sem nunca interpretar
`.st` na hora da consulta, e sem nunca usar IA/heurística estatística/fuzzy
matching em nenhuma camada.

## Arquitetura em camadas

```text
export textual (ReadOnlyTextExporter, já validado)
        ↓
1. Parser ST determinístico (tokenização → statements → declarações)
        ↓
2. Resolução de símbolos (7 níveis de prioridade, nunca escolhe por
   suposição em ambiguidade) + classificação read/write
        ↓
3. Índices JSON estáveis em disco (symbols/references/calls/type-index/
   read-write-index/...)
        ↓
4. Consultas determinísticas sobre os JSONs (find symbol/reads/writes/
   calls/callers) — nunca reprocessa ST
        ↓
5. Parser de intenção em linguagem natural controlada (PT/EN, ~28 padrões
   fixos, zero IA/fuzzy) → uma das 5 operações acima
        ↓
6. Resposta fundamentada nas evidências (templates fixos, nunca geração
   livre)
        ↓
7. API Python pública, tipada e estável (mastertool_bridge.ProjectIndex)
        ↓
8. Servidor MCP fino (8 tools, sem lógica de domínio própria)
```

Cada seta é uma fronteira de commit isolado, testado e validado
separadamente — ver `## Histórico de commits` abaixo.

## 1–3. Parser, resolução de símbolos, índices (`src/mastertool_bridge/indexer/`)

- `st_lexer.py` — tokenizador hand-written (Python 3, sem dependência de
  IronPython), preserva arquivo/linha/coluna por token. Única extensão desde
  a criação: reconhecimento de endereço de hardware `AT %QX54.0` (bloqueio
  técnico demonstrado antes de alterar).
- `declaration_parser.py` / `gvl_parser.py` / `dut_parser.py` — parsers
  tolerantes de `declaration.st`: cabeçalho de POU
  (`PROGRAM`/`FUNCTION_BLOCK`/`FUNCTION`), GVL (sem cabeçalho de POU, blocos
  `VAR_GLOBAL` diretos, pragma `{attribute 'qualified_only'}`), e DUT
  (`TYPE ... END_TYPE`: `STRUCT`, alias simples, e ENUM reconhecido como tipo
  existente mas fora de escopo — `kind="unknown"`, nunca lança exceção).
- `statement_parser.py` — reconhece statements (atribuição,
  IF/CASE/FOR/WHILE/REPEAT/RETURN) e chamadas (posicionais, nomeadas
  `:=`/`=>`, dotted) em `implementation.st`. Cadeias pontuadas com índice de
  array no meio (`GVL.Array[i].Membro`) viram uma única referência, com o
  conteúdo do índice escaneado recursivamente como referência própria.
- `symbol_resolver.py` — prioridade de resolução de 7 níveis (variável/
  parâmetro local → instância de FUNCTION_BLOCK → GVL explícita → GVL
  implícita → tipo → unresolved), generalizada para caminhar por cadeias de
  N≥2 segmentos (`GVL.Instancia.Membro.SubMembro...`), incluindo membros de
  STRUCT (via `TypeSymbol`) e alias (com detecção de ciclo). **Nunca escolhe
  um candidato arbitrariamente em ambiguidade.**
- `reference_resolver.py` / `call_resolver.py` — classificação read/write/
  read_write por regra fixa de contexto sintático + operador
  (`:=`→read, `=>`→write, `VAR_IN_OUT`→read_write quando o parâmetro formal é
  resolvível); chamadas de método sobre instância NUNCA afirmadas como
  "resolved" (o modelo de dados não acessa a árvore de métodos de um FB —
  limitação documentada, não escondida).
- `export_loader.py: build_static_index()` — orquestra tudo, escreve 11
  artefatos em `output_dir`: `symbols.json`, `type-index.json`,
  `diagnostics.json`, `source-map.json`, `calls.json`, `references.json`,
  `resolved-calls.json`, `callers.json`, `resolved-references.json`,
  `read-write-index.json`, `resolution-diagnostics.json`.

### Estados de resolução

`resolved` / `partially_resolved` (prefixo comprovado, sufixo não —
ex. tipo reconhecido mas membro não encontrado) / `ambiguous` (2+
candidatos, nunca escolhido) / `unresolved`.

## 4. Consultas determinísticas (`indexer/query.py`)

`find_symbol`/`find_reads`/`find_writes`/`find_calls`/`find_callers`, cada
uma operando SOMENTE sobre os JSONs já gerados (nunca reprocessa ST).
`find_calls` responde "o que a POU X chama" (saída); `find_callers`
responde "quem chama X" (entrada) — direções deliberadamente opostas,
travadas por teste de contrato explícito. Confiança por evidência é um
mapeamento fixo a partir do `resolution_state` (resolved→high,
partially_resolved→medium, ambiguous→low, unresolved→none) — nunca
heurística estatística.

## 5–6. Linguagem natural controlada (`query_intent.py`, `query_response.py`)

`parse_query_intent(texto)` reconhece um conjunto FECHADO de ~28 padrões
(comando canônico em inglês + ~5 frases em português por operação, mais
frases de "uso" que ficam deliberadamente `ambiguous` — nunca escolhe
leitura ou escrita por suposição — e frases de explicação/raciocínio que
ficam `unsupported`, fora de escopo desta etapa). Zero IA, zero fuzzy
matching, zero correção ortográfica além de dobra determinística de
acento/caixa (com distinção de confiança `exact`/`normalized` conforme
precisou ou não dessa dobra).

`answer_query(pergunta, bundle)` converte o resultado determinístico em uma
resposta textual fundamentada (`QueryAnswer`: status/summary/evidence/
limitations), com templates de string fixos por família de operação —
nunca geração livre. Limitações de resolução parcial são propagadas
honestamente (nunca escondidas), e desaparecem automaticamente quando a
resolução melhora numa fatia posterior (comprovado: a fatia de DUT/STRUCT
não precisou tocar em nenhum template de resposta).

## 7. API Python pública (`src/mastertool_bridge/api.py`)

```python
from mastertool_bridge import ProjectIndex

index = ProjectIndex.open(index_dir)   # carrega uma vez; InvalidIndexError se invalido
index.find_symbol(name) -> QueryResult
index.find_reads(name) -> QueryResult
index.find_writes(name) -> QueryResult
index.find_calls(name) -> QueryResult
index.find_callers(name) -> QueryResult
index.ask(question) -> QueryAnswer
index.metadata -> dict
```

Camada de EMPACOTAMENTO pura (nunca duplica lógica de resolução/consulta/
formatação — tudo isso continua 100% em `indexer/*`). `QueryEvidence`
tipa os 7 campos universais de qualquer evidência (node_id/file/line/
column/resolution_state/resolved_symbol/confidence) e preserva o resto em
`extra`, com round-trip sem perda. `ProjectIndexError`/`InvalidIndexError`/
`UnsupportedSchemaError` (esta última reservada para uso futuro — nenhum
artefato hoje carrega marcador de schema para checar de verdade).

## 8. Servidor MCP (`src/mastertool_bridge/mcp_server.py`)

8 tools finas sobre a API pública: `open_project_index`,
`get_index_metadata`, `find_symbol`, `find_reads`, `find_writes`,
`find_calls`, `find_callers`, `ask_project`. Princípio central: "tool MCP →
valida argumentos → chama `ProjectIndex` → devolve `to_dict()`" — nenhuma
lógica semântica no servidor. Cada tool recebe `index_dir` explícito; um
cache interno evita reabrir/reler o índice do disco em chamadas repetidas.
Erros sempre viram dict estruturado (`{"error": ..., "message": ...}`),
nunca uma exceção crua atravessa o protocolo. Dependência nova `mcp` (SDK
oficial) — única exceção deliberada à disciplina de zero-dependência
seguida em todo o resto do indexer. Console script: `mastertool-bridge-mcp`.

## Como executar

```bash
# 1. Gerar o índice a partir de um export já validado
python -c "
from mastertool_bridge.indexer.export_loader import build_static_index
build_static_index('workspace/exports/<run>/', 'workspace/analysis/<indice>/')
"

# 2. Consultas via CLI
python -m mastertool_bridge.indexer query symbol Estado_OP --index-dir workspace/analysis/<indice>
python -m mastertool_bridge.indexer ask "onde Estado_OP é escrito?" --index-dir workspace/analysis/<indice> --json

# 3. Via API Python
python -c "
from mastertool_bridge import ProjectIndex
index = ProjectIndex.open('workspace/analysis/<indice>')
print(index.ask('o que MainPrg chama?').to_dict())
"

# 4. Servidor MCP (stdio — configurar no cliente MCP, ex. Claude Desktop/Code)
mastertool-bridge-mcp
# ou: python -m mastertool_bridge.mcp_server
```

## Limitações conhecidas (honestas, não bloqueantes)

- **ENUM/UNION/INTERFACE**: reconhecidos como tipo existente (`kind="unknown"`),
  mas não indexados por membro — cadeias que tentam acessar um "membro" de
  enum ficam `partially_resolved`, nunca `unresolved` silenciosamente e
  nunca `resolved` por suposição.
- **Métodos de FUNCTION_BLOCK**: o modelo de dados não acessa a árvore de
  métodos de uma instância — chamadas de método nunca são afirmadas como
  "resolved", sempre `ambiguous`/`unresolved` com diagnóstico explicando o
  motivo.
- **Chamadas de biblioteca externa** (`SysTimeCore.SysTimeGetUs`,
  `CONCAT`, etc.): honestamente `unresolved` — não há catálogo de símbolos
  de biblioteca padrão CODESYS indexado.
- **Perguntas compostas, "por quê"/"como funciona", resumo de lógica de
  POU**: fora de escopo desta etapa (`status="unsupported"`) — pertencem a
  uma camada futura, ainda não construída.
- **`UnsupportedSchemaError`**: reservada para uso futuro; nenhum artefato
  JSON gerado hoje carrega um marcador de versão de schema para checar de
  verdade.

## Validação

Ver relatorios de validacao internos (nao publicados) para o relatório de validação completo
(histórico de commits, métricas de teste, amostragem manual, política de
segurança).

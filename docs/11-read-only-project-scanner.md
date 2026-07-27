# ReadOnlyProjectScanner — varredura recursiva somente leitura

> Estado: **validado em runtime real com sucesso total** (2026-07-23,
> contra `ExemploPlanta V1.0.project`, checksums 8/8 OK): 117 nós, 100%
> completos, 0 erros, `scan_complete=true`, árvore inteira mapeada,
> incluindo confirmação cruzada `Device → Plc Logic → Application` ==
> `active_application` (mesmo `object_guid`). Fase de descoberta
> estrutural considerada encerrada. `tree_walker.py` permanece suspenso —
> ver detalhes completos em `docs/api/mastertool-api-observations.md`.

## Motivação

Os probes 05-10 confirmaram, um índice por execução, que a cadeia
`get_children(False)` → `Count` → indexador nativo →
`is_folder`/`type`/`guid`/`get_name(False)` funciona identicamente em
qualquer nível da árvore (raiz e nós filhos, ver
[api/mastertool-api-observations.md](api/mastertool-api-observations.md)).
Em vez de continuar criando um probe por índice, este componente
generaliza a mesma cadeia já confirmada para uma varredura completa da
árvore, com limites obrigatórios, isolamento de falhas por ramo e saída
inteiramente serializável.

## Decisão de arquitetura

`tree_walker.py` **não foi reativado**. Foi criado um módulo novo e
independente:

```text
scripts/mastertool/common/read_only_project_scanner.py
```

Depois que o scanner for validado em runtime real, `tree_walker.py`
poderá ser removido, transformado em fachada, ou passar a consumir
internamente o novo scanner — nenhuma dessas decisões foi tomada nesta
entrega.

## API

```python
class ReadOnlyProjectScanner(object):
    def __init__(self, max_depth=8, max_total_nodes=5000,
                max_children_per_node=256, expected_root_count=None):
        ...

    def scan(self, project):
        """project ja resolvido (ex.: projects.primary). Retorna um dict
        100% serializavel — nunca lanca excecao."""
```

Funções auxiliares (índices, seção "Índices auxiliares" abaixo):

```python
flatten_tree(tree) -> list
build_node_indexes(flat_nodes) -> dict
```

Usa exclusivamente, em qualquer nível da árvore:

```python
node.get_children(False)
collection.Count
collection[index]
node.get_name(False)
node.is_folder
node.type
node.guid
```

Nunca usa `dir()`, `find()`, `active_application`, documentos textuais,
configuração de hardware, ou qualquer API online/de escrita/compilação.

### `is_folder` não impede `get_children(False)`

Já confirmado em runtime real (probes 06/09/10) que objetos com
`is_folder == False` podem ter filhos (ex.: `Device`, um objeto com
`is_folder=False`, tem 2 filhos: "Plc Logic" e um segundo nó ainda não
identificado). Por isso o scanner tenta `get_children(False)` em **todo**
nó alcançado, até os limites configurados — `is_folder` é tratado
puramente como metadado semântico, nunca como sinal de "não ter filhos".

## Percurso: DFS iterativo, sem recursão Python

O scanner usa uma pilha explícita (`stack`), nunca chamadas Python
recursivas nem `GetEnumerator()`/`iter()`/`list()`/compreensão sobre a
coleção CLR. Os filhos de cada nó são lidos em ordem crescente
(`0..Count-1`, via `range()` Python local) e empilhados em ordem reversa,
de forma que o `pop()` da pilha os processe na ordem crescente correta —
o resultado preserva a ordem de descoberta.

Forma permitida:

```python
count = collection.Count
for index in range(count):
    child = collection[index]
```

Continuam **proibidos**: `for child in collection`, `list(collection)`,
`iter(collection)`, `collection.GetEnumerator()`,
`[child for child in collection]`.

## Identificação de nó

`node_id` é construído **exclusivamente** a partir do caminho de índices
Python percorrido (`root`, `root/0`, `root/1/0`, ...) — nunca a partir do
GUID. Alguns nós podem não expor GUID, o GUID pode falhar isoladamente, e
o caminho de índices representa exatamente a navegação realizada.

A **raiz** (`projects.primary`, uma `IScriptProject`) tem uma identidade
distinta dos demais nós: como já confirmado no probe 04
(`IScriptProject` não implementa `IScriptObject`), a raiz só expõe
`path`/`is_root` (chave `"root"` de nível superior no resultado), nunca
`name`/`is_folder`/`type`/`guid`. Todos os demais nós da árvore (`children`
retornados por `get_children`, instâncias de `IScriptObject`) usam os 4
campos de identidade completos.

## Limites obrigatórios

| Limite | Efeito quando excedido |
|--------|--------------------------|
| `max_depth` | Nó além do limite aparece na árvore (identidade lida), mas seus próprios filhos **não são buscados** (`collection.state = "not_attempted_depth_limit"`) |
| `max_total_nodes` | **Interrompe o scan inteiro** antes de indexar a coleção que ultrapassaria o limite; tudo já coletado é preservado (`scan_complete: false`) |
| `max_children_per_node` | **Nenhum filho daquela coleção é indexado** (`collection.state = "children_limit_exceeded"`); o resto do scan continua normalmente |
| `Count < 0` | Coleção rejeitada (`invalid_negative_count`), nenhum filho indexado |

`expected_root_count` é **opcional** e validado **somente na raiz**. Uma
divergência registra `root_count_mismatch` mas **não interrompe** o
scan — o valor observado (nunca o esperado) é sempre o limite real da
enumeração. Isso evita que adicionar um objeto legítimo ao projeto seja
interpretado como falha permanente da API (mesmo princípio já usado em
`ProjectTreeAdapter`).

## Modelo de falhas

- Falha em `get_children`/`Count`/interface de contagem/`Count` negativo:
  marca **apenas aquele nó** como tendo coleção falha; o resto do scan
  continua normalmente por outros ramos.
- Falha no indexador (`collection[index]`): interrompe **apenas aquela
  coleção** no primeiro índice que falhar (não tenta os seguintes,
  coleção pode estar instável), mas os filhos já lidos com sucesso antes
  da falha permanecem no resultado; o nó pai fica marcado
  `"partial_indexing"`.
- Falha isolada em um campo de identidade (`name`/`is_folder`/`type`/
  `guid`): nunca impede a leitura dos demais campos do mesmo nó, nem de
  qualquer outro nó.
- Nenhum `repr()`/`str()`/`.ToString()` é chamado em objeto CLR
  desconhecido — toda serialização passa por
  `capabilities.build_representation()`.

## Detecção de ciclos e duplicidades

Conservadora, por design:

- Se o mesmo `object_guid` aparecer em **dois caminhos diferentes** (sem
  relação de ancestralidade), é registrado como `duplicate_object_guid`
  (informativo) — **ambos os nós permanecem** no relatório, a descida de
  ambos continua normalmente.
- A descida só é bloqueada (`cycle_detected: true`, `get_children` NÃO
  chamado naquele nó) quando o mesmo `object_guid` já aparece entre os
  **ancestrais do próprio nó** na cadeia atual — evidência suficiente de
  ciclo real.
- `handle` nunca é usado como identificador (estabilidade entre execuções
  não comprovada — ver probe 03).

## Saída

Ver o schema completo no docstring do módulo. Resumo:

```json
{
  "schema_version": "1.0",
  "scanner": {"mode": "read_only", "max_depth": 6, "max_total_nodes": 2000, "max_children_per_node": 128},
  "root": {"path": {...}, "is_root": {...}},
  "statistics": {"total_nodes": 0, "complete_nodes": 0, "partial_nodes": 0, "failed_nodes": 0, "scan_complete": false, ...},
  "tree": {"node_id": "root", "depth": 0, "identity": {}, "collection": {...}, "children": [...]},
  "errors": [],
  "limits": {"max_depth_reached": false, "max_total_nodes_reached": false, "max_children_per_node_reached": false},
  "safety_declaration": {...}
}
```

Nenhum proxy do ScriptEngine, `ExtendedObject`, coleção CLR ou referência
viva ao projeto aparece no resultado — apenas dicionários, listas,
strings, números, booleanos e `None`.

## Índices auxiliares

Gerados separadamente (funções `flatten_tree()`/`build_node_indexes()`),
não fazem parte do retorno de `scan()`:

- `flat_nodes`: lista achatada de todos os nós (`node_id`,
  `parent_node_id`, `depth`, `index`, `name`, `type_guid`, `object_guid`,
  `child_count`).
- `node-indexes`: `nodes_by_name`/`nodes_by_type_guid`/
  `nodes_by_object_guid` (dict de string → lista de `node_id`).

## Script de validação

```text
scripts/mastertool/probes/12_validate_recursive_scanner.py
```

Wrapper fino: resolve `projects.primary`, cria o scanner com limites
conservadores desta primeira execução
(`max_depth=6, max_total_nodes=2000, max_children_per_node=128,
expected_root_count=4` — este último específico de
`ExemploPlanta V1.0.project`), executa uma única varredura, e grava:

```text
workspace/logs/<timestamp>_12_validate_recursive_scanner/
├── .mastertool-bridge-run
├── report.json          # metadados, estatísticas, limites, declaração de segurança
├── report.md            # resumo legível + árvore resumida
├── project-tree.json    # árvore completa
├── flat-nodes.json      # lista achatada
├── node-indexes.json    # índices por nome/type_guid/object_guid
├── errors.json          # somente erros/advertências estruturados
└── checksums.sha256
```

Validado **externamente** (fora do MasterTool): dry-run com `projects`
ausente (degradação graciosa) e uma segunda execução com uma árvore
sintética via fakes (espelhando a estrutura real já confirmada:
Project Settings / Device → Plc Logic + Bus / Project Information /
__VisualizationStyle) produzindo os 8 artefatos esperados, estatísticas
corretas (`total_nodes=7`, `scan_complete=true`, `0` erros) e índices
corretos. **Execução real dentro do MasterTool ainda não autorizada.**

## Configuração

`config/scanner-defaults.yaml` define os limites genéricos padrão
(`max_depth: 8`, `max_total_nodes: 5000`, `max_children_per_node: 256`,
`expected_root_count: null`) e, separadamente, os limites mais
conservadores usados apenas na primeira validação real (seção
`first_validation_run`, com `expected_root_count: 4` — específico de
`ExemploPlanta V1.0.project`, nunca fixado no bloco genérico).

## Próxima fase (não implementada nesta entrega)

Depois que a árvore completa estiver confirmada em runtime real:

1. **Leitura textual**: identificar objetos candidatos a texto e testar,
   com poucos objetos representativos primeiro,
   `has_textual_declaration`/`textual_declaration.text`/
   `has_textual_implementation`/`textual_implementation.text`.
2. **Export completo**: `workspace/exports/<timestamp>/manifest.json` +
   `project-tree.json` + `objects/{programs,function-blocks,functions,
   methods,actions,gvls,duts}/` + `errors.json` + `checksums.sha256`.
3. **Teste futuro de escrita** (só depois da exportação textual
   funcionar, em cópia descartável): criar um FB de teste, escrever
   declaração/implementação, salvar cópia, `build()`, coletar mensagens —
   sem download nem sessão online.

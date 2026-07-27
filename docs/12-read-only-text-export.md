# ReadOnlyTextExporter — exportação textual somente leitura

> Estado: **validado em runtime real com sucesso total** (2026-07-23,
> contra `ExemploPlanta V1.0.project`, checksums 158/158 OK): 92 nós, 100%
> completos, 0 erros, 68 objetos com texto (68 declarações + 14
> implementações), 66.360 caracteres exportados, preservação exata
> confirmada por amostragem (SHA-256 recalculado manualmente bateu). 225
> testes unitários passando (`tests/unit/test_read_only_text_exporter.py`
> tem 38 deles; suíte completa: 225 passed, 1 skipped). `tree_walker.py`
> permanece suspenso — ver detalhes completos em
> `docs/api/mastertool-api-observations.md`.

## Motivação

`common/read_only_project_scanner.py: ReadOnlyProjectScanner` confirmou em
runtime real (117 nós, 0 erros, `ExemploPlanta V1.0.project`) que a cadeia
`get_children(False)` → `Count` → indexador → `is_folder`/`type`/`guid`/
`get_name(False)` funciona identicamente em qualquer nível da árvore. A
mesma execução também confirmou, por confirmação cruzada de `object_guid`,
que `Device → Plc Logic → Application` é o mesmo objeto que
`projects.primary.active_application` desde o probe 04.

Esta fase estende a mesma filosofia de navegação para dois objetivos novos:

1. Entrar pela **Application** (não pela raiz do projeto) — a subárvore que
   de fato contém o código de aplicação (POUs, GVLs, DUTs, tasks, etc.);
2. Além dos metadados estruturais já cobertos pelo scanner, ler o
   **conteúdo textual** (declaração e implementação ST) de cada objeto que
   confirmar, de forma explícita e tri-state, que possui esse conteúdo —
   via `common/capabilities.py`, nunca por suposição.

## Decisão de arquitetura

Módulo novo e independente, autocontido:

```text
scripts/mastertool/common/read_only_text_exporter.py
```

Os helpers de navegação/identidade já aprovados no scanner
(`probe_node_identity`, `probe_property_via_representation`,
`_implements_count_bearing_interface`, o mesmo vocabulário de estados de
coleção) foram **copiados localmente** para este módulo, em vez de
importados de `read_only_project_scanner.py`. Decisão deliberada: manter o
exportador textual autocontido, sem acoplamento acidental com o scanner —
que o `AGENTS.md` trata como módulo estável/validado e não deve ser
alterado ou tornado dependência de um módulo mais novo e ainda não
validado em runtime real.

`tree_walker.py` **não foi tocado** e continua suspenso.

## API

```python
class ReadOnlyTextExporter(object):
    def __init__(self, max_depth=8, max_total_nodes=2000,
                max_children_per_node=256, max_text_objects=500,
                max_document_characters=2000000, max_total_characters=25000000,
                expected_application_name=None,
                expected_application_type_guid=None,
                expected_application_guid=None):
        ...

    def export(self, application, output_directory=None):
        """application ja resolvida (ex.: project.active_application).
        Retorna um dict 100% serializavel — nunca lanca excecao."""
```

Funções módulo-level auxiliares:

```python
flatten_tree(tree) -> list
build_text_index(flat_nodes) -> dict
write_text_export_artifacts(export_result, output_directory) -> list
```

Usa exclusivamente, em qualquer nó da subárvore:

```python
node.get_children(False)
collection.Count
collection[index]
node.get_name(False)
node.is_folder
node.type
node.guid
node.has_textual_declaration       # getattr isolado, tri-state
node.textual_declaration           # SO SE has_* confirmado True
node.textual_declaration.text      # SO SE textual_declaration confirmado
node.has_textual_implementation    # mesma regra, para implementação
node.textual_implementation
node.textual_implementation.text
```

### APIs proibidas (lista fechada)

Nunca usa `dir()` como fonte de verdade, `find()`, `replace()`, `append()`,
`get_line()`, `create_pou()`, `create_gvl()`, `create_dut()`, `build()`,
`rebuild()`, `clean()`, `generate_code()`, `save()`, `save_as()`, `close()`,
nenhum setter, `device_repository`/`online`, PLCopen XML, nem qualquer
normalização/strip do texto lido. Ver a regra inviolável correspondente em
`AGENTS.md`.

## Regras de descoberta de texto: portões obrigatórios

`has_textual_declaration`/`has_textual_implementation` são **portões
obrigatórios**, nunca acesso especulativo:

1. Sonda o indicador booleano (`has_textual_declaration` ou
   `has_textual_implementation`) isoladamente, via `capabilities.probe_member`.
2. Só avança para o passo seguinte se o indicador vier **confirmado e
   estritamente `True`** (não apenas *truthy*) — qualquer outro resultado
   (`unsupported`, `unknown`, `False` confirmado, ou valor não-booleano)
   interrompe a leitura textual **daquele documento**, sem tentar
   `textual_declaration`/`textual_implementation` de forma alguma.
2. Só então sonda o objeto documento (`textual_declaration` ou
   `textual_implementation`) isoladamente.
3. Só então sonda `.text` do documento — e só o serializa se vier
   confirmado como **string nativa** (`_STRING_TYPES`, cobre `str`/`unicode`
   em IronPython 2.7). Nenhum `repr()`/`str()`/`.ToString()` é chamado sobre
   o próprio objeto documento — apenas sobre a string já confirmada de
   `.text`, e mesmo assim via os limites (abaixo), nunca formatação livre.

Declaração e implementação são tratadas **inteiramente em separado**: uma
falha em uma nunca impede a tentativa da outra no mesmo nó. A descoberta de
texto roda em **todo** nó visitado — inclusive folhas sem filhos — e
**antes** da navegação de filhos daquele nó, de forma que documentos
textuais sejam sondados independentemente do resultado da coleção.

### Estados possíveis de um documento (`doc_state`)

| Estado | Significado |
|--------|-------------|
| `not_applicable` | Indicador ausente/`False`/não tentado por outro motivo não listado abaixo |
| `indicator_confirmed_false` | Indicador confirmado, valor `False` |
| `indicator_unsupported` | `has_textual_*` não existe neste objeto (`AttributeError`) |
| `indicator_unknown` | Falha ao ler o indicador por outro motivo |
| `indicator_not_boolean` | Indicador leu um valor, mas não é `bool` |
| `document_unsupported` / `document_unknown` | Indicador confirmado `True`, mas o objeto documento não pôde ser obtido |
| `document_null` | Objeto documento veio `None` mesmo com indicador `True` |
| `text_unsupported` / `text_unknown` | `.text` não pôde ser lido do documento |
| `text_not_string` | `.text` leu um valor, mas não é string nativa |
| `document_size_limit_exceeded` | Texto lido, mas excede `max_document_characters` — **não salvo** |
| `max_total_characters_reached` | Texto lido, mas salvá-lo excederia `max_total_characters` — **não salvo**, bloqueia novas leituras textuais dali em diante |
| `max_text_objects_reached` | Limite de objetos com texto já atingido — nenhuma nova leitura tentada (nem indicador) |
| `saved` | Único estado em que o texto foi de fato lido, contabilizado e (na camada de escrita) gravado em disco |

Qualquer estado diferente de `saved` nunca impede a navegação estrutural do
nó nem a descoberta de texto em outros nós.

## Limites obrigatórios

| Limite | Efeito quando excedido |
|--------|--------------------------|
| `max_depth` | Igual ao scanner: nó além do limite aparece na árvore, filhos não buscados |
| `max_total_nodes` | Igual ao scanner: aborta o scan inteiro, preserva tudo já coletado |
| `max_children_per_node` | Igual ao scanner: nenhum filho daquela coleção é indexado |
| `max_text_objects` | Quantidade de **objetos** (não documentos) com pelo menos 1 documento salvo — ao atingir, nenhuma nova leitura textual é tentada (metadados estruturais continuam normalmente) |
| `max_document_characters` | Documento individual (declaração OU implementação) que excede o limite não é salvo — registrado com `character_length` conhecido mas `text: null` |
| `max_total_characters` | Soma de caracteres de todos os documentos já salvos; ao seria excedido por um novo documento, este não é salvo e nenhuma leitura textual nova é tentada dali em diante |

`max_text_objects` conta **objetos** com pelo menos um documento salvo, não
documentos individuais: se declaração E implementação forem ambas salvas no
mesmo nó, isso incrementa o contador **uma única vez** para aquele nó
(`node_saved_any`).

## Modelo de falhas

Idêntico ao scanner para navegação estrutural (coleção/indexador/campo de
identidade isolados — ver `docs/11-read-only-project-scanner.md`), com uma
regra adicional: falha ao sondar ou ler um documento textual isola **apenas
aquele documento** (declaração OU implementação, nunca as duas de uma vez
pelo mesmo motivo) — nunca aborta a navegação do nó, de seus irmãos, ou do
scan inteiro. Apenas `max_total_nodes` aborta o scan inteiro.

## Identidade da Application: portão do script, não da classe

A classe genérica (`ReadOnlyTextExporter`) **apenas relata** divergência de
identidade da Application via `application_identity_mismatch` — ela nunca
decide abortar sozinha. A decisão de abortar **antes de qualquer leitura de
texto** cabe ao script chamador (`probes/13_validate_text_exporter.py`):
ele sonda a identidade da Application isoladamente
(`exporter._probe_application_identity`), decide, e só chama `.export()` de
fato se a identidade bater com os `expected_*` configurados. Isso implica
uma pequena duplicação de leitura (a identidade é sondada de novo,
internamente, dentro de `.export()`) — aceita deliberadamente porque é a
única forma de garantir a ordem exigida sem alterar o fluxo interno de
`export()`.

## Estrutura de saída

`export()` retorna um dict serializável com a árvore completa da subárvore
da Application **e o texto de cada documento em memória**
(`node["text"]["declaration"/"implementation"]["text"]`), permitindo que a
camada de escrita (abaixo) seja pura e separada. Resumo do schema (ver
docstring do módulo para o completo):

```json
{
  "schema_version": "1.0",
  "exporter": {"mode": "read_only", "max_depth": 8, "max_total_nodes": 2000, ...},
  "application_identity": {"name": {...}, "type_guid": {...}, "object_guid": {...}},
  "application_identity_mismatch": [],
  "output_directory": null,
  "statistics": {"total_nodes": 0, "text_object_count": 0, "declarations_saved": 0, "implementations_saved": 0, "total_characters_saved": 0, "scan_complete": false, ...},
  "tree": {"node_id": "application", "depth": 0, "identity": {}, "collection": {...}, "text": {"declaration": null, "implementation": null}, "children": [...]},
  "errors": [],
  "limits": {"max_depth_reached": false, "max_total_nodes_reached": false, "max_text_objects_reached": false, "max_total_characters_reached": false, ...},
  "safety_declaration": {...}
}
```

`node_id` usa o prefixo `application` no lugar de `root`
(`application`, `application/0`, `application/0/3`, ...) — mesma construção
exclusivamente por caminho de índices já usada no scanner.

### Artefatos gravados por `probes/13_validate_text_exporter.py`

```text
workspace/exports/<timestamp>_13_validate_text_exporter/
├── manifest.json           # metadados da execução + configuração do exportador
├── report.json             # identidade da Application, estatísticas, limites, declaração de segurança
├── report.md               # resumo legível + árvore resumida (com [decl=... impl=...] por nó)
├── application-tree.json   # árvore completa retornada por export() (inclui os textos)
├── flat-objects.json       # lista achatada (flatten_tree)
├── text-index.json         # somente nós com pelo menos 1 documento salvo (build_text_index)
├── errors.json             # somente erros/advertências estruturados
├── checksums.sha256
└── objects/
    └── <node_id_seguro>__<nome_sanitizado>/
        ├── metadata.json        # doc_state/character_length/byte_length/sha256/error por documento
        ├── declaration.st       # se has_declaration
        └── implementation.st    # se has_implementation
```

Se a identidade da Application divergir dos `expected_*`, o script grava
`manifest.json`/`report.json`/`report.md`/`errors.json` normalmente,
registra `aborted_due_to_identity_mismatch: true` e **não grava**
`application-tree.json`/`flat-objects.json`/`text-index.json`/`objects/`
(nenhum documento textual foi lido).

## Preservação de texto: sem normalização, SHA-256, byte vs. caractere

Nenhuma normalização de fim de linha, `strip()`, ou qualquer alteração é
aplicada ao texto lido, em nenhum ponto do fluxo (leitura em memória nem
escrita em disco). Para cada documento salvo:

- `character_length`: `len(text_value)` sobre a string Python já confirmada;
- `byte_length`: `len(text_value.encode("utf-8"))` — pode diferir de
  `character_length` sempre que houver caracteres não-ASCII (acentuação);
- `sha256`: hash do texto (via `common/checksums.sha256_text`), calculado
  sobre a mesma string em memória, **antes** de qualquer escrita em disco —
  permite comparar depois se o arquivo gravado é bit-a-bit idêntico ao que
  foi lido.

A escrita usa `codecs.open(path, "wb", "utf-8")` (grava bytes UTF-8, sem
tradução de fim de linha do modo texto) — confirmado byte-a-byte na
validação sintética com texto contendo CRLF, linha em branco com espaços, e
acentuação (`ç`, `é`).

## Separação pura/impura

`export()` é **100% puro em relação a disco** — nunca abre um arquivo,
mesmo quando recebe `output_directory` (usado apenas para registrar, no
resultado, onde a camada de escrita *deveria* gravar). Toda a navegação, as
decisões de portão (indicadores booleanos), e os limites são testáveis
inteiramente com fakes em memória.

A escrita em disco é uma função módulo-level **separada**,
`write_text_export_artifacts(export_result, output_directory)`, que recebe
o dict já retornado por `export()` e **apenas serializa o que já foi
decidido** — nunca vê proxies do ScriptEngine, nunca toma nenhuma decisão de
leitura. Essa separação permitiu 33 testes cobrindo toda a navegação/decisão
sem tocar disco, e testes isolados da escrita usando `tmp_path`.

## Script de validação

```text
scripts/mastertool/probes/13_validate_text_exporter.py
```

Wrapper fino: reutiliza `projects.primary` e `project.active_application`
(ambos já confirmados em execuções anteriores — probes 04/12), sonda a
identidade da Application **antes** de qualquer leitura textual, aborta sem
chamar `.export()` se divergir dos `expected_*` desta primeira validação
(específicos de `ExemploPlanta V1.0.project`, nunca fixados na classe
genérica):

```text
max_depth = 8
max_total_nodes = 1000
max_children_per_node = 128
max_text_objects = 300
max_document_characters = 1000000
max_total_characters = 15000000
expected_application_name = "Application"
expected_application_type_guid = "639b491f-5557-464c-af91-1471bac9f549"
expected_application_guid = "00000000-0000-0000-0000-000000000001"
```

Se a identidade bater, executa **uma única exportação completa** e grava os
artefatos acima.

### Validação realizada até agora (SEM MasterTool real)

- `py_compile` OK em todos os arquivos novos;
- 38 testes unitários passando (`tests/unit/test_read_only_text_exporter.py`;
  suíte completa do repositório: 225 passed, 1 skipped);
- Dry-run externo do probe 13 sem `projects` definido: degrada
  graciosamente, registra erro, grava relatório, **não lança exceção**;
- Validação com árvore sintética via `runpy` + monkeypatch de
  `builtins.projects`, cobrindo: 1 POU com declaração+implementação
  multiline (acentos, CRLF, linha em branco com espaços — texto e hash
  SHA-256 conferidos byte-a-byte em memória e em disco), 1 GVL só com
  declaração, 1 DUT só com declaração, 1 pasta sem texto (indicadores
  confirmados `False`), 1 objeto com texto vazio (`character_length=0`,
  arquivo de 0 bytes em disco), 1 objeto com erro simulado no indicador de
  declaração (`indicator_unknown`, não trava o export), 1 objeto com erro
  simulado no indicador de implementação (idem). Identidade da Application
  batendo com os `expected_*` reais (não aborta); 4 diretórios `objects/`
  gravados com `metadata.json` + `declaration.st` (+ `implementation.st`
  quando aplicável); conteúdo em disco idêntico byte-a-byte ao original.
  Artefatos gerados limpos via `scripts/maintenance/safe_clean_artifact.py --confirm`.

**A execução real dentro do MasterTool, contra `ExemploPlanta V1.0.project`,
ainda não aconteceu.** Isso depende de aprovação explícita e execução
manual do usuário dentro do MasterTool — o mesmo protocolo já seguido para
o scanner recursivo antes de sua validação real.

### Limitações conhecidas desta entrega

1. Não foi testado explicitamente um cenário de colisão de nomes
   sanitizados iguais em nós diferentes na camada de escrita (ex.: dois
   objetos chamados `"A/B"` e `"A_B"` colidindo após sanitização) — cenário
   extremamente improvável, já que o diretório de cada objeto usa
   `<node_id_seguro>__<nome_sanitizado>` e `node_id` (baseado em índices) já
   é único por construção.
2. Não foi testado limite real de profundidade extrema (milhares de
   níveis) nem overhead de performance com volumes grandes de texto —
   apenas fakes pequenos em memória. Validação de escala fica para a
   execução real dentro do MasterTool.
3. O campo `text` de cada nó na árvore retornada por `export()` inclui o
   texto completo do documento em memória (necessário para a camada de
   escrita separada) — intencional, mas significa que o resultado inteiro
   de `export()` pode ser grande em memória para árvores com muito texto;
   mitigado pelos limites `max_document_characters`/`max_total_characters`.

## Configuração

`config/text-export-defaults.yaml` define os limites genéricos padrão
(`max_depth: 8`, `max_total_nodes: 2000`, `max_children_per_node: 256`,
`max_text_objects: 500`, `max_document_characters: 2000000`,
`max_total_characters: 25000000`, `expected_application_*: null`) e,
separadamente, os limites mais conservadores usados apenas na primeira
validação real (seção `first_validation_run`, com os `expected_application_*`
específicos de `ExemploPlanta V1.0.project` — nunca fixados no bloco genérico).

## Próxima fase (não implementada nesta entrega)

Depois que esta exportação textual estiver confirmada em runtime real
(mesmo protocolo já seguido para o scanner estrutural):

1. **Indexação de símbolos**: a partir do texto exportado (declarações
   principalmente), extrair um índice de nomes de variáveis/tipos/blocos de
   função usados, para permitir busca cruzada entre objetos sem reabrir o
   MasterTool.
2. **Busca em linguagem natural**: sobre o índice de símbolos + o texto
   exportado, permitir perguntas do tipo "onde é usado o FB X" ou "quais
   POUs escrevem na variável Y" — camada inteiramente externa (Python 3,
   `src/mastertool_bridge/`), nunca dentro do MasterTool.
3. **Comparação entre exports**: diff textual entre duas exportações da
   mesma Application em momentos diferentes (ex.: antes/depois de uma
   alteração manual no MasterTool), reaproveitando os hashes SHA-256 já
   calculados por documento para pular comparação de conteúdo idêntico.
4. **Escrita controlada futura** (só depois de tudo acima funcionar, e só
   em cópia descartável, sob aprovação humana explícita): usar a mesma
   identificação de nó (`node_id`) para localizar um objeto e escrever uma
   nova declaração/implementação de teste, seguido de `save_as` em cópia,
   `build()`, coleta de mensagens — sem download nem sessão online. Nada
   disso está implementado ou planejado em detalhe nesta entrega.

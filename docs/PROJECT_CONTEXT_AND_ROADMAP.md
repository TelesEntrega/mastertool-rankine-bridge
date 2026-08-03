# MasterTool AI Bridge — Contexto consolidado, decisões e roadmap

> **PONTEIRO — o "estado atual" descrito abaixo é o de 24/07/2026.** Ele
> antecede as fases W1 a W9, em que a autoria controlada foi provada contra o
> MasterTool X. O estado vigente está em
> [`CURRENT_STATUS.md`](CURRENT_STATUS.md) e o plano corrente em
> [`ROADMAP.md`](ROADMAP.md). Este documento continua valendo como registro das
> **decisões** tomadas e do raciocínio por trás delas.

**Data de consolidação:** 24/07/2026  
**Projeto:** `mastertool-rankine-bridge`  
**Ambiente-alvo:** MasterTool IEC XE 3.63 / MT8500, baseado em CODESYS  
**Projeto PLC usado nas validações:** cópia de `ExemploPlanta V1.0.project`  
**Estado atual:** aquisição estrutural e exportação textual somente leitura concluídas e validadas em runtime real; StaticProjectIndexer completo (parser → resolução → consultas → linguagem natural controlada → API Python → servidor MCP) — ver seção 25  
**Checkpoint Git:** commit `14e4bbb` (root-commit, 2026-07-24) — ver seção 16  
**Baseline StaticProjectIndexer:** commit `523f443` (2026-07-24), tag `v0.1.0` — ver seção 25  
**Próxima fase:** validação operacional concluída (ver seção 25); roadmap de Ladder/FBD/SFC/engenharia por agentes registrado, fase L0 em andamento — ver seção 26 e `docs/14-ladder-roadmap.md`

---

## 1. Objetivo do projeto

O `mastertool-rankine-bridge` está sendo desenvolvido para criar uma ponte segura entre projetos do MasterTool IEC XE e ferramentas externas em Python 3, Git e, futuramente, assistência por IA/MCP.

A visão de longo prazo é permitir:

- inspecionar projetos MasterTool de forma estruturada;
- exportar POUs, GVLs, DUTs, estruturas, declarações e implementações;
- pesquisar símbolos, referências, chamadas, leituras e escritas;
- gerar documentação técnica;
- comparar versões e change sets;
- preparar alterações controladas;
- criar ou modificar objetos somente em cópias descartáveis;
- compilar a cópia e coletar diagnósticos;
- submeter alterações à revisão humana antes de qualquer uso real.

O projeto não deve operar diretamente sobre o projeto produtivo nem assumir APIs não comprovadas.

---

## 2. Princípios de segurança e engenharia

### 2.1. Regras permanentes

- Nunca modificar o projeto real.
- Nunca versionar arquivos `.project` reais.
- Nunca versionar `ExemploPlanta V1.0.project`.
- Nunca versionar arquivos `.compileinfo`.
- Usar cópias descartáveis para qualquer teste futuro de escrita.
- Não realizar download para CLP.
- Não executar `force`.
- Não iniciar ou utilizar sessão online.
- Não alterar configuração de hardware nesta etapa.
- Não usar setters ou métodos de escrita sem prova estática e validação controlada.
- Não inventar nomes de APIs.
- Separar aquisição no MasterTool de análise externa em Python 3.
- Registrar logs, manifests, checksums e declaração de segurança em cada execução.
- Não fazer commit sem solicitação explícita.

### 2.2. Política de descoberta de API

A descoberta segue duas fontes:

1. **Evidência estática**
   - reflection-only sobre assemblies;
   - inspeção de interfaces e assinaturas;
   - extração de membros literais;
   - nenhuma execução de código de plugins durante a análise estática.

2. **Evidência em runtime**
   - probes mínimos no MasterTool;
   - whitelists explícitas;
   - limites rígidos;
   - nenhum fallback especulativo.

### 2.3. Política de serialização segura

Nunca usar em objetos CLR desconhecidos:

- `repr()`;
- `str()`;
- `.ToString()`;
- interpolação implícita;
- concatenação que force conversão.

Os helpers centrais devem continuar usando representação estrita e tipos conhecidos:

- `build_representation()`;
- `python_type_info()`;
- `dotnet_type_info()`;
- `strict_object_repr()`.

Objetos retornados pelo ScriptEngine nunca devem sair em JSON como proxies vivos.

---

## 3. Ambiente confirmado

### 3.1. Instalação

```text
C:\Program Files (x86)\Altus\MT8500 3.63\
```

### 3.2. Runtime de scripts

O runtime interno é IronPython:

```python
sys.platform == "cli"
```

`sys.version` retorna o banner observado:

```text
MT8500.exe MasterTool IEC XE, ScriptEngine.plugin 4.1.0.0
```

### 3.3. Objetos globais confirmados

```text
projects
system
```

Tipos observados:

```text
projects → ScriptProjects
system   → SystemImpl
```

`projects.primary` existe e retorna:

```text
ExtendedObject[IScriptProject]
```

A propriedade `.path` é legível.

---

## 4. Descobertas estáticas de API

As interfaces principais foram encontradas em `ScriptEngine3.dll`.

### 4.1. Projeto e árvore

Interfaces confirmadas:

- `IScriptProject`
- `IScriptTreeObject`
- `IScriptObject`
- `IScriptTextDocument`

#### `IScriptProject`

```text
active_application
get_children(recursive: bool)
find(...)
```

#### `IScriptObject`

```text
get_name(resolve_localized: bool)
type
guid
is_folder
has_textual_declaration
textual_declaration
has_textual_implementation
textual_implementation
```

#### `IScriptTextDocument`

```text
text
get_line()
append()
```

Somente `.text` foi autorizado e utilizado na fase de leitura textual.

### 4.2. Build

`ScriptApplication` expõe:

```text
build()
rebuild()
clean()
generate_code()
```

Esses métodos ainda não foram usados.

### 4.3. Mensagens de compilação

`ScriptMessage` expõe:

```text
text
severity
object
position
```

### 4.4. Dumper oficial

Foi localizada estaticamente a assinatura:

```text
Assembly: ScriptEngine.plugin 4.1.0.0
Type: _3S.CoDeSys.ScriptEngine.ScriptEngine
Method: DumpScriptingApi
```

Características:

- método público de instância;
- virtual;
- retorno `void`;
- 7 parâmetros;
- somente `outputWriter` obrigatório;
- 6 parâmetros opcionais com default `null`.

Uma tentativa controlada de localizar a instância no escopo confirmado falhou com segurança. Nenhuma chamada foi realizada.

Estado:

```text
status: unavailable_from_confirmed_script_scope
required: false
blocking: false
```

Não procurar essa API por nomes inventados ou service locators especulativos.

---

## 5. Particularidade crítica dos proxies dinâmicos

Os objetos são proxies DLR:

```text
ExtendedObject<T>
```

Foi confirmado que:

```python
dir(projects.primary)
```

pode retornar vazio mesmo quando `getattr()` funciona.

Conclusão permanente:

> `dir()` é diagnóstico, não fonte autoritativa da API.

A descoberta deve continuar baseada em catálogo estático, whitelist e acesso explícito.

---

## 6. Arquitetura atual

```text
MasterTool / IronPython
│
├── scripts/mastertool/common/
│   ├── capabilities.py
│   ├── project_tree_adapter.py
│   ├── read_only_project_scanner.py
│   ├── read_only_text_exporter.py
│   └── helpers de segurança
│
├── scripts/mastertool/probes/
│   ├── probes iniciais
│   ├── 08_validate_root_adapter.py
│   ├── 09_device_children_collection.py
│   ├── 10_device_first_child_identity.py
│   ├── 12_validate_recursive_scanner.py
│   └── 13_validate_text_exporter.py
│
└── workspace/
    ├── logs/
    └── exports/

Python 3 externo
│
├── testes
├── validação do repositório
├── análise dos exports
└── futura indexação semântica
```

O arquivo:

```text
scripts/mastertool/common/tree_walker.py
```

permanece suspenso e não foi reativado.

---

## 7. Política de capacidades

Estados:

```text
confirmed
unsupported
unknown
```

Regras:

```text
AttributeError        → unsupported
qualquer outra falha  → unknown
leitura concluída     → confirmed
```

Whitelist relevante:

```python
{
    "projects": ["primary"],
    "project": ["path", "is_root", "handle", "active_application"],
    "system": []
}
```

`.type` e `.guid` não pertencem diretamente ao root `IScriptProject`; nós filhos `IScriptObject` expõem esses membros.

---

## 8. Resultados de navegação estrutural

### 8.1. Root do projeto

Confirmado:

```text
projects.primary.path
projects.primary.is_root == True
projects.primary.handle == 0
projects.primary.active_application
```

`handle == 0` não deve ser tratado como identificador persistente.

### 8.2. Application por atalho

```text
proxy: ExtendedObject[IScriptObject]
tipo CLR: _3S.CoDeSys.ScriptDriverProjects.ScriptObject
name: Application
guid: 00000000-0000-0000-0000-000000000001
```

O GUID coincidiu com:

```text
ExemploPlanta V1.0.Device.Application.00000000-0000-0000-0000-000000000001.compileinfo
```

### 8.3. Filhos diretos do root

`projects.primary.get_children(False)` retornou:

```text
System.Collections.Generic.List<IExtendedObject<IScriptObject>>
```

Interfaces confirmadas incluem `IList`, `ICollection`, `IReadOnlyList` e `IReadOnlyCollection`, genéricas e não genéricas.

`Count == 4`.

| Índice | Nome | is_folder | type GUID | object GUID |
|---:|---|---:|---|---|
| 0 | Project Settings | False | `8753fe6f-4a22-4320-8103-e553c4fc8e04` | `6470a90f-b7cb-43ac-9ae5-94b2338b4573` |
| 1 | Device | False | `225bfe47-7336-4dbc-9419-4105a7c831fa` | `ec2ca054-836f-492f-a95f-f296c4785352` |
| 2 | Project Information | False | `085afe48-c5d8-4ea5-ab0d-b35701fa6009` | `11c0fc3a-9bcf-4dd8-ac38-efb93363e521` |
| 3 | `__VisualizationStyle` | False | `8e687a04-7ca7-42d3-be06-fcbda676c5ef` | `5cce1091-f902-4a48-9357-89653e070a0d` |

### 8.4. Filhos de Device

```text
Device.get_children(False)
Count == 2
```

Primeiro filho:

```text
name: Plc Logic
is_folder: False
type: 40b404f9-e5dc-42c6-907f-c89f4a517386
guid: ab0a1c6e-c69e-41f6-bb2a-9601c4989dbb
```

Estrutura completa observada:

```text
Device
├── Plc Logic
│   └── Application
└── Configuration
    └── NX3005
```

### 8.5. Caminho da Application

```text
root/1/0/0
```

Equivalente a:

```text
Project → Device → Plc Logic → Application
```

O GUID do caminho hierárquico coincide com `active_application.guid`:

```text
00000000-0000-0000-0000-000000000001
```

---

## 9. ProjectTreeAdapter

Arquivo:

```text
scripts/mastertool/common/project_tree_adapter.py
```

Características:

- profundidade inicial 1;
- uma chamada a `get_children(False)`;
- uma leitura de `Count`;
- acesso por índices Python;
- nenhuma iteração direta da coleção CLR;
- limites de quantidade;
- falhas por campo isoladas;
- saída serializável.

Validação real em `probes/08_validate_root_adapter.py`:

- `Count == 4`;
- quatro identidades corretas;
- `path` e `is_root` confirmados.

---

## 10. ReadOnlyProjectScanner

### 10.1. Arquivos

```text
scripts/mastertool/common/read_only_project_scanner.py
scripts/mastertool/probes/12_validate_recursive_scanner.py
tests/unit/test_read_only_project_scanner.py
config/scanner-defaults.yaml
docs/11-read-only-project-scanner.md
```

### 10.2. Arquitetura

- DFS iterativo;
- pilha explícita;
- sem recursão Python;
- sem `iter()`, `GetEnumerator()` ou `list()` sobre coleção CLR;
- `node_id` baseado em caminho de índices;
- falhas isoladas por ramo;
- limites obrigatórios;
- detecção conservadora de ciclos;
- duplicidades sem assumir ciclo.

### 10.3. Resultado real

```text
117 nós
117 completos
0 parciais
0 falhos
0 erros
```

Profundidade:

```text
6 expandida
4 nós em profundidade 7 registrados, sem expansão
```

Limites:

```text
max_depth_reached: true
max_total_nodes_reached: false
max_children_per_node_reached: false
```

Checksums:

```text
8/8 OK
```

### 10.4. Árvore resumida

```text
Project
├── Project Settings
├── Device
│   ├── Plc Logic
│   │   └── Application
│   │       ├── SystemGVLs/UserGVLs
│   │       ├── Task Configuration
│   │       ├── SystemPOUs/UserPOUs
│   │       ├── SystemEvents
│   │       ├── Blocos
│   │       ├── Estruturas
│   │       ├── RK_HOOK
│   │       ├── TPVs
│   │       └── outros objetos de software
│   └── Configuration
│       └── NX3005
│           ├── rede/dispositivos
│           ├── EtherNet_IP_Scanner
│           ├── inversores
│           └── parâmetros
├── Project Information
└── __VisualizationStyle
```

Tipos relevantes observados:

- dispositivos: `225bfe47-...`
- pastas de POU: `738bea1e-...`
- POUs folha: `6f9dac99-...`
- GVLs: `ffbfa93a-...`
- tasks: `98a2708a-...`
- POUs de task: `413e2a7d-...`
- Application: `639b491f-...`

Usar os GUIDs completos do artefato real quando forem necessários como contrato.

---

## 11. ReadOnlyTextExporter

### 11.1. Arquivos

```text
scripts/mastertool/common/read_only_text_exporter.py
scripts/mastertool/probes/13_validate_text_exporter.py
tests/unit/test_read_only_text_exporter.py
config/text-export-defaults.yaml
docs/12-read-only-text-export.md
```

### 11.2. Escopo

O exportador inicia em:

```python
projects.primary.active_application
```

Percorre somente a subárvore de software da `Application`.

APIs usadas:

```python
node.has_textual_declaration
node.textual_declaration
document.text

node.has_textual_implementation
node.textual_implementation
document.text
```

Nenhum método de escrita foi usado.

### 11.3. Preservação

- sem `.strip()`;
- sem normalizar linhas;
- sem reindentar;
- sem formatar ST;
- sem ordenar;
- sem alterar comentários;
- SHA-256 por documento;
- tamanho em caracteres e bytes.

### 11.4. Estrutura do export

```text
workspace/exports/<timestamp>_text_export/
├── .mastertool-bridge-run
├── manifest.json
├── report.json
├── report.md
├── application-tree.json
├── flat-objects.json
├── text-index.json
├── errors.json
├── checksums.sha256
└── objects/
    └── <node_id>__<nome>/
        ├── metadata.json
        ├── declaration.st
        └── implementation.st
```

### 11.5. Resultado real

```text
92 nós da Application
92 completos
0 falhos
0 erros
68 objetos com texto
68 declarações
14 implementações
66.360 caracteres
0 limites atingidos
```

Checksums:

```text
158/158 OK
```

Validação manual:

- SHA-256 do FB `Valvula_Simples` recalculado;
- hash coincidente;
- preservação exata confirmada por amostragem.

---

## 12. Achados de auditoria e correções

### 12.1. Declaração de segurança incompleta

Campos faltantes:

```text
text_document_access
text_document_write
replace_called
append_called
get_line_called
active_application_used
```

**Status:** corrigido.

### 12.2. `metadata.json` fora do schema

Campos faltantes:

```text
schema_version
parent_node_id
depth
index
identity
runtime
errors
```

**Status:** corrigido.

### 12.3. Colisão de caminho por `startswith()`

`application/1` capturava erros de `application/10` e `application/11`.

**Status:** boundary corrigido e teste de regressão incluído.

### 12.4. `text-index.json` fora do contrato

O schema produzido inicialmente diferia do especificado. Os testes validavam o formato errado de forma autorreferente.

**Status:** schema e testes corrigidos; índice do run real regenerado sem nova leitura do MasterTool.

### 12.5. Contagem documental incorreta

Correção:

```text
38 testes no módulo novo
225 passed, 1 skipped na suíte final
```

---

## 13. Estado final de validação

```text
python -m pytest -q
→ 225 passed, 1 skipped
```

```text
python scripts/maintenance/validate-repository.py
→ [OK] Repositório consistente.
```

Também foram realizados:

- `py_compile`;
- grep por métodos proibidos;
- dry-run externo;
- limpeza via `safe_clean_artifact.py --confirm`;
- confirmação de `tree_walker.py` intocado;
- nenhum commit.

---

## 14. Higiene de artefatos

`workspace/` é ignorado pelo Git.

Sentinel obrigatório:

```text
.mastertool-bridge-run
```

Limpeza:

```text
safe_clean_artifact.py --confirm
```

Regras:

- caminho exato;
- dentro de `workspace`;
- sentinel obrigatório;
- sem glob destrutivo;
- sem apagar artefatos por padrão.

---

## 15. Estado atual

### Implementado e validado

- descoberta do ambiente;
- catálogo estático parcial;
- capacidades;
- serialização segura;
- navegação do root e Device;
- confirmação da Application;
- adapter de profundidade 1;
- scanner estrutural recursivo;
- exportador textual;
- logs, reports e checksums;
- testes;
- documentação.

### Ainda não implementado

- lexer ST;
- parser de declarações;
- tabela de símbolos;
- referências;
- chamadas;
- leitura/escrita;
- busca em linguagem natural;
- diff semântico;
- change sets;
- criação/edição de POU;
- salvamento de cópia;
- build;
- coleta de mensagens;
- integração MCP.

### Ainda não autorizado

- escrita;
- compilação;
- `find()`;
- criação de objetos;
- salvar projeto;
- hardware;
- online/download/force.

---

## 16. Checkpoint Git

**Status: CONCLUÍDO.** Commit criado em 2026-07-24:

```text
14e4bbb — feat: add validated read-only MasterTool tree and text export
```

Root-commit (primeiro commit do repositório), 198 arquivos, 19.455
inserções, sem remote configurado. Working tree confirmado limpo logo
após o commit.

Não incluído (confirmado antes do commit):

- `workspace/`;
- exports;
- logs;
- `.project`;
- `.compileinfo`;
- temporários do MasterTool.

Antes do commit:

```bash
python -m pytest -q
python scripts/maintenance/validate-repository.py
git status
git diff --check
```

---

# 17. Próxima fase — StaticProjectIndexer

## 17.1. Objetivo

```text
workspace/exports/<run>/
        ↓
StaticProjectIndexer
        ↓
índices determinísticos
```

Operar somente sobre arquivos exportados. Não abrir o MasterTool.

## 17.2. Saídas planejadas

```text
analysis/<timestamp>_static_index/
├── manifest.json
├── symbols.json
├── references.json
├── calls.json
├── read-write-index.json
├── type-index.json
├── diagnostics.json
├── source-map.json
├── report.json
└── checksums.sha256
```

## 17.3. Símbolos

- `PROGRAM`;
- `FUNCTION_BLOCK`;
- `FUNCTION`;
- GVL;
- DUT;
- `STRUCT`;
- `ENUM`;
- aliases;
- variáveis locais e globais;
- `VAR_INPUT`;
- `VAR_OUTPUT`;
- `VAR_IN_OUT`;
- `VAR_TEMP`;
- `VAR_STAT`;
- constantes;
- arrays;
- referências;
- instâncias de FB;
- parâmetros.

## 17.4. Referências

- leitura;
- escrita;
- atribuição;
- membro;
- índice de array;
- chamada de função;
- chamada de método;
- instância de FB;
- parâmetros de entrada/saída/IN_OUT;
- tipos;
- GVL;
- enum;
- constantes.

## 17.5. Pipeline obrigatório

Não usar somente regex.

```text
carregamento do export
→ tokenização ST
→ linha/coluna
→ comentários
→ blocos VAR
→ declarations
→ statements
→ tabela de símbolos
→ resolução parcial
→ read/write
→ índices
```

Exemplo:

```iecst
IF Estado_OP = 3 THEN
    Estado_OP := 4;
END_IF;
```

- primeiro `Estado_OP`: leitura;
- segundo: escrita.

Exemplo:

```iecst
MeuFB(
    IN_VALOR := Estado_OP,
    OUT_VALOR => Estado_Aux
);
```

- `MeuFB`: chamada a resolver;
- `Estado_OP`: leitura;
- `Estado_Aux`: escrita.

---

## 18. Roadmap restante

### Fase 6 — Inventário externo

- carregar export;
- validar checksums;
- mapear arquivo ↔ objeto;
- source map;
- diagnósticos.

### Fase 7 — Lexer ST

- identificadores;
- keywords;
- números;
- strings;
- operadores;
- `:=`;
- `=>`;
- pontuação;
- comentários `//` e `(* ... *)`;
- pragmas;
- linha e coluna.

### Fase 8 — Parser de declarações

- tipo de POU;
- blocos `VAR`;
- nome;
- tipo;
- inicializador;
- array;
- escopo;
- direção;
- atributo;
- localização.

Saídas:

```text
symbols.json
type-index.json
```

### Fase 9 — Statements e chamadas

- atribuições;
- chamadas;
- `IF`, `CASE`, loops;
- membros;
- índices;
- argumentos nomeados;
- `=>`;
- instâncias.

Saídas:

```text
calls.json
references.json
```

### Fase 10 — Leituras e escritas

- LHS de `:=`: escrita;
- RHS: leitura;
- condições: leitura;
- input: leitura;
- output: escrita;
- IN_OUT: leitura e escrita;
- classificação com confiança.

Saída:

```text
read-write-index.json
```

### Fase 11 — Resolução de símbolos

Prioridade:

1. local;
2. parâmetro;
3. variável da POU;
4. instância;
5. GVL explícita;
6. GVL implícita;
7. global;
8. tipo;
9. unresolved.

Ambiguidades devem ser registradas.

### Fase 12 — Validação manual

Casos úteis:

- `Estado_OP`;
- `IN_PERM_DESCARGA`;
- `Sincroniza_Balancas`;
- `Var_SD`;
- `Sessao_BP`;
- `Valvula_Simples`;
- arrays;
- estruturas;
- `:=` e `=>`.

### Fase 13 — Busca determinística

```text
find symbol Estado_OP
find writes Estado_OP
find reads IN_PERM_DESCARGA
find calls Sincroniza_Balancas
find callers Valvula_Simples
find type Sessao_BP
```

### Fase 14 — Linguagem natural

```text
Onde Estado_OP é escrito?
Quais POUs usam IN_PERM_DESCARGA?
Quem chama Sincroniza_Balancas?
```

Fluxo:

```text
pergunta → intenção → consulta determinística → evidências → resposta
```

### Fase 15 — Comparação entre exports

- adicionados/removidos/renomeados;
- declaração/implementação;
- símbolos;
- read/write;
- chamadas;
- risco.

### Fase 16 — Documentação

- documentação de POUs;
- mapa de chamadas;
- GVLs;
- matriz read/write;
- diagramas;
- impacto.

### Fase 17 — Change sets

Formato externo com:

- projeto/objeto alvo;
- hashes de precondição;
- operações;
- validação requerida.

Não aplicar se os hashes divergirem.

### Fase 18 — Primeiro teste de escrita

Somente em cópia descartável:

```text
criar FB_AI_TESTE
→ declaração
→ implementação
→ salvar cópia
→ reabrir
→ confirmar persistência
→ build
```

Sem chamada, hardware, online, download ou force.

### Fase 19 — Compilação controlada

Usar futuramente:

```text
build()
```

Coletar:

```text
ScriptMessage.text
ScriptMessage.severity
ScriptMessage.object
ScriptMessage.position
```

Comparar baseline e pós-alteração.

### Fase 20 — Edição de objetos existentes

Somente após teste sintético:

- backup;
- hashes;
- preview;
- revisão;
- cópia;
- build;
- diff;
- nunca projeto real automático.

### Fase 21 — IA/MCP

A IA poderá:

- consultar;
- explicar;
- propor;
- gerar change sets;
- analisar build;
- documentar.

A IA não poderá:

- editar sem change set;
- ignorar hashes;
- salvar no projeto real;
- operar online;
- download;
- force.

---

## 19. Gates

### Gate A — aquisição estrutural

```text
CONCLUÍDO
```

### Gate B — exportação textual

```text
CONCLUÍDO
```

### Gate C — indexação estática

Pendente:

- lexer;
- declarations;
- statements;
- símbolos;
- referências;
- read/write;
- validação manual.

### Gate D — busca confiável

Pendente:

- consultas determinísticas;
- evidência por linha;
- ambiguidades explícitas.

### Gate E — escrita sintética

Pendente:

- API de criação;
- cópia;
- persistência;
- build.

### Gate F — alteração existente

Pendente:

- change set;
- hashes;
- backup;
- diff;
- build;
- revisão.

### Gate G — integração assistida

Pendente:

- políticas;
- auditoria;
- autorização;
- rollback;
- nenhuma operação online.

---

## 20. Riscos conhecidos

### ST complexo

- extensões CODESYS;
- pragmas;
- namespaces;
- métodos;
- propriedades;
- actions;
- interfaces;
- ponteiros;
- referências;
- inicializadores.

Mitigação:

- parser incremental;
- diagnostics;
- resolução parcial;
- não inventar semântica.

### `type_guid` compartilhado

Não classificar apenas por GUID. Combinar:

- nome;
- pai;
- caminho;
- metadados.

### GUID ausente

Usar:

- `node_id`;
- caminho;
- nome;
- tipo;
- parent.

Nunca usar `handle` como persistente.

### Testes autorreferentes

Mitigar com:

- testes de contrato;
- fixtures independentes;
- inspeção real;
- validação cruzada;
- hashes recalculados.

---

## 21. Checklist de retomada

1. Ler este arquivo.
2. Rodar:
   ```bash
   git status
   git log --oneline -5
   python -m pytest -q
   python scripts/maintenance/validate-repository.py
   ```
3. Confirmar:
   - `workspace/` ignorado;
   - nenhum `.project` staged;
   - `tree_walker.py` suspenso;
   - nenhuma operação online.
4. Localizar o export textual validado.
5. Não abrir MasterTool para indexação.
6. Trabalhar somente nos arquivos exportados.
7. Não iniciar escrita antes dos Gates C e D.

---

## 22. Próxima ação imediata

Validação operacional ponta a ponta concluída (seção 25). Roadmap de
Ladder/FBD/SFC/documentação automática/agentes/change sets/geração de
projetos registrado por decisão explícita do usuário (2026-07-24) —
`docs/14-ladder-roadmap.md`. Fase corrente: **L0 (inventário e
classificação)**, com autorização do usuário para trabalhar de forma
autônoma nos gates que não dependem de execução real no MasterTool (ver
seção 26). Próxima ação concreta: rodar
`probes/14_inventory_graphic_pous.py` dentro do MasterTool real — só o
usuário pode executar.

---

## 23. Estado em uma linha

```text
Aquisição estrutural real concluída → exportação textual real concluída → StaticProjectIndexer completo e validado (parser → resolução → consultas → linguagem natural → API Python → MCP) → validação operacional dupla concluída → roadmap Ladder/FBD/SFC/agentes registrado, fase L0 em andamento.
```

---

## 24. Manutenção deste documento

Atualizar ao final de cada marco com:

```text
data
commit
fase
resultado
novas APIs confirmadas
riscos
próximo gate
```

Este arquivo é o checkpoint narrativo central do projeto.

---

## 25. Marco — StaticProjectIndexer completo, do parser ao servidor MCP (2026-07-24)

**Data:** 2026-07-24
**Commits:** 12, sequenciais, `36dda15`→`523f443` (sobre a base de `14e4bbb`+`264aeb1`;
14 commits no total no repositório) — lista completa e detalhada em
`RELATORIO-VALIDACAO-v0.1.0.md`. Tag de baseline: `v0.1.0`.
**Fase:** encerramento do gate de indexação semântica + primeira integração
externa (API Python + MCP), como gate de estabilização antes de novos
recursos — autorizado explicitamente pelo usuário.

**Resultado:** pipeline completo e validado end-to-end:
parser ST determinístico (nunca só regex) → resolução de símbolos em 7
níveis de prioridade (GVL/FB/tipo/STRUCT-DUT, nunca escolhe por suposição
em ambiguidade) → classificação read/write por regra fixa → 11 artefatos
JSON estáveis → 5 consultas determinísticas (`find symbol/reads/writes/
calls/callers`) → parser de intenção em PT/EN controlado (~28 padrões
fixos, zero IA/fuzzy) → respostas fundamentadas em evidências (templates
fixos) → API Python pública e estável (`mastertool_bridge.ProjectIndex`)
→ servidor MCP fino (8 tools, sem lógica de domínio própria). Cada
commit foi verificado independentemente por mim antes de commitar
(re-executar testes, ler o diff real, re-rodar smoke test contra o export
real de `ExemploPlanta V1.0.project`) — nunca aceito só o autorrelato de um
subagente. Dois bugs reais foram encontrados e corrigidos por essa
disciplina de verificação, não pelos subagentes que implementaram as
fatias originais: direção semântica trocada de `find_calls` (commit
`8124ed0`) e `load_query_bundle` não recarregando os tipos DUT/STRUCT do
disco (corrigido dentro do commit `e44d4a6`). Ver `docs/13-static-project-indexer.md`
(arquitetura completa) e `RELATORIO-VALIDACAO-v0.1.0.md` (relatório de
validação, métricas de teste, amostragem manual).

**Novas APIs confirmadas:** nenhuma API nova do MasterTool/CODESYS — este
marco opera inteiramente sobre o export textual já validado, nunca abre o
MasterTool.

**Riscos/limitações conhecidas:** ENUM/UNION/INTERFACE reconhecidos como
tipo existente mas não indexados por membro (fica `partially_resolved`,
nunca escondido); métodos de FUNCTION_BLOCK e chamadas de biblioteca
externa honestamente não resolvidos (sem catálogo de símbolos padrão
CODESYS); perguntas compostas/explicativas fora de escopo
(`status="unsupported"`); `UnsupportedSchemaError` reservada para uso
futuro (nenhum artefato hoje carrega marcador de schema real). Nenhum
risco de segurança novo — toda a camada é somente leitura sobre arquivos
já exportados, `mastertool_bridge.indexer.*`/`api.py`/`mcp_server.py`
nunca importam nem chamam nada de `scripts/mastertool/` (que continua
sendo o único código com acesso real ao ScriptEngine).

**Próximo gate:** retomar `scripts/mastertool/00_smoke_test.py` no
MasterTool real, como nova trilha controlada — validar a cadeia completa
MasterTool → export → índice → consulta → MCP contra uma execução real.

---

## 26. Marco — Roadmap de Ladder, documentação e agentes registrado; fase L0 iniciada (2026-07-24)

**Data:** 2026-07-24
**Commit:** ver histórico a partir deste marco (registrado após a validação
operacional da seção 25)
**Fase:** encerrado o gate de validação operacional (seção 25); usuário
registrou um roadmap completo e extenso (Ladder → FBD/SFC → grafos de
engenharia → documentação automática → agentes especializados → change
sets → geração de módulos/projetos, v0.2→v1.0) e autorizou trabalho
autônomo contínuo ("pode ir trabalhando sozinho em tudo que tu conseguir,
não precisa ficar me chamando toda hora").

**Resultado:** roadmap completo registrado em `docs/14-ladder-roadmap.md`
(conteúdo verbatim fornecido pelo usuário, com uma seção 8 adicional de
"Estado de execução" para registro vivo de progresso). Reconhecimento
offline imediato (sem tocar o MasterTool, usando os dois exports reais já
capturados e validados): 25 objetos candidatos a implementação NÃO
textual (Ladder/FBD/SFC) identificados em `flat-objects.json`
(`has_declaration=true`, `has_implementation=false`, mesmo `type_guid` de
POUs ST confirmadas) — incluindo `StartPrg`/`UserPrg`, chamados por
`MainPrg` mas nunca antes examinados quanto à própria implementação.

**Regra de execução autônoma explicitamente reafirmada pelo próprio
roadmap do usuário**: "Implementar a semântica antes de conhecer o
formato real criaria uma arquitetura baseada em suposições" — cada fase
além de L0 (análise offline) depende de uma execução real dentro do
MasterTool, que só o usuário pode disparar. Trabalho autônomo continua
dentro desse limite: análise offline, ferramentas/scripts preparados
(nunca executados por mim dentro do MasterTool), testes, documentação —
sempre com a mesma disciplina de verificação independente já usada em
toda a trilha ST (ver [[mastertool-rankine-bridge-autonomous-gates]]).

**Novas APIs confirmadas:** nenhuma ainda — reconhecimento desta entrada
foi inteiramente offline, sobre dados já capturados.

**Riscos/limitações conhecidas:** `has_implementation=false` é evidência,
não prova, de implementação gráfica (também pode significar "sem
implementação nenhuma"); a linguagem real de cada candidato (Ladder vs.
FBD vs. SFC) só pode ser confirmada dentro do MasterTool.

**Próximo gate:** usuário executar `probes/14_inventory_graphic_pous.py`
(quando existir — ver estado de execução em `docs/14-ladder-roadmap.md`)
dentro do MasterTool real.

# MasterTool AI Bridge — Roadmap de Ladder, documentação e engenharia por agentes

> Estado: **registrado em 2026-07-24, sobre a baseline `v0.1.0`** (parser ST
> completo, validado em duas execuções reais independentes — ver
> `docs/13-static-project-indexer.md` e relatorios de validacao internos (nao publicados)).
> Fase corrente: **L0 (Inventário e classificação) — CONCLUÍDA e validada
> em execução real dentro do MasterTool 3.63 em 2026-07-24 15:56**. O probe
> `probes/14_inventory_graphic_pous.py` rodou ao vivo e produziu
> `{supported: 14, partially_supported: 25, unsupported: 24, unknown: 29}`
> sobre 92 objetos — **idêntico objeto a objeto** ao resultado da
> implementação offline independente (0 divergências em 92/92 `node_id`).
> Os 25 candidatos `partially_supported` incluem `StartPrg`/`UserPrg`
> (chamadas por `MainPrg`, nunca antes examinadas em detalhe);
> `MainPrg`/`SpecialVariablesPrg` confirmados `supported`. **Gate de L1
> aberto.**
>
> **L1 executada em 2026-07-27, mas NÃO fechada.** A sondagem confirmou a
> rota `export_xml` → **PLCopen XML** (achada pelo tipo
> `_3S.CoDeSys.PLCopenXML.ConflictResolve` numa assinatura real). Porém a
> enumeração por reflexão .NET não enxerga as extensões dinâmicas do
> ScriptEngine — provado pelo caso-controle `textual_declaration`, membro
> funcional que não apareceu na lista. Logo o resultado negativo é
> inconclusivo e **o gate de L2 segue fechado**. Ver seção "Estado de
> execução" ao final deste documento para o registro vivo de progresso e a
> evidência completa.
>
> **Regra permanente desta trilha**: nenhuma fase além de L0 (análise
> offline sobre dados já exportados) pode avançar sem uma execução real
> dentro do MasterTool 3.63 — só o usuário pode rodar scripts dentro do
> MasterTool. Implementar a semântica antes de conhecer o formato real
> criaria uma arquitetura baseada em suposições (mesma regra já seguida em
> toda a trilha ST/`ReadOnlyProjectScanner`/`ReadOnlyTextExporter`).

## 1. Visão do produto

O objetivo final do `mastertool-ai-bridge` é executar sobre qualquer projeto MasterTool compatível e produzir no computador uma representação completa, portátil e consultável do projeto.

Essa representação deverá permitir:

* navegar por toda a árvore do projeto;
* compreender lógica em ST, Ladder, FBD e SFC;
* localizar símbolos, leituras, escritas e chamadas;
* responder perguntas sobre funcionamento e falhas;
* criar agentes especializados de suporte técnico;
* gerar descritivos lógicos e manuais de operação;
* comparar versões;
* propor alterações;
* criar e validar projetos por meio de agentes de IA.

Fluxo final pretendido:

```text
Projeto MasterTool
→ snapshot completo
→ modelo canônico
→ índices semânticos
→ grafos de engenharia
→ consultas e agentes
→ documentos
→ change sets
→ geração e validação de projetos
```

---

# 2. Baseline atual — v0.1.0

A versão atual já possui uma fundação validada para Structured Text:

```text
MasterTool real
→ árvore estrutural
→ exportação textual
→ parser ST
→ símbolos e DUT/STRUCT
→ referências
→ read/write
→ chamadas e chamadores
→ consultas determinísticas
→ perguntas controladas
→ respostas fundamentadas
→ API Python
→ servidor MCP
```

A cadeia foi validada em duas execuções reais independentes.

Estado por linguagem:

| Linguagem       | Estado atual                                    |
| --------------- | ----------------------------------------------- |
| Structured Text | Interpretação semântica avançada                |
| Ladder          | Objeto e declaração parcialmente inventariáveis |
| FBD             | Implementação gráfica ainda não interpretada    |
| SFC             | Implementação gráfica ainda não interpretada    |
| CFC             | Não investigado                                 |
| IL              | Não investigado                                 |

A principal lacuna atual é a implementação gráfica.

---

# 3. Arquitetura alvo para linguagens gráficas

Ladder, FBD e SFC não devem ser convertidos por OCR ou análise de imagem.

A aquisição deve encontrar uma representação estrutural confiável:

```text
MasterTool
→ XML, API gráfica ou formato exportado
→ modelo gráfico bruto
→ representação intermediária canônica
→ análise semântica
→ índices unificados
```

O modelo canônico deve permitir que ST e Ladder produzam os mesmos tipos de evidência:

```text
Symbol
Reference
Read
Write
ReadWrite
Call
Caller
Condition
Assignment
Network
SourceLocation
Diagnostic
```

Assim, uma consulta como:

```text
Onde MotorLigado é escrito?
```

deverá retornar tanto ocorrências em ST quanto bobinas Ladder.

---

# 4. Trilha Ladder

## Fase L0 — Inventário e classificação

### Objetivo

Identificar todas as POUs gráficas existentes no projeto e classificá-las por linguagem.

### Entregas

```text
graphic-language-inventory.json
ladder-objects.json
unsupported-objects.json
```

Para cada objeto:

* `node_id`;
* nome;
* GUID;
* caminho na árvore;
* linguagem;
* declaração textual disponível;
* implementação textual disponível;
* tipo de representação disponível;
* capacidade de exportação;
* status de suporte.

### Estados

```text
supported
partially_supported
unsupported
unknown
```

### Critério de aprovação

O sistema deve localizar uma POU Ladder conhecida e diferenciá-la corretamente de ST, FBD e SFC.

### Commit sugerido

```text
feat: add graphic language object inventory
```

---

## Fase L1 — Descoberta da representação Ladder

### Objetivo

Descobrir como o MasterTool expõe uma implementação Ladder real.

### Estratégias, em ordem

1. Verificar propriedades confirmadas do objeto.
2. Inspecionar interfaces por reflection-only.
3. Procurar API oficial de exportação de objeto.
4. Procurar XML PLCopen ou CODESYS.
5. Procurar estrutura de redes, elementos, pinos e conexões.
6. Exportar uma POU Ladder isolada, quando suportado.
7. Comparar arquivos antes e depois de uma pequena alteração manual.

### Probes somente leitura

```text
14_inventory_graphic_pous.py
15_probe_ladder_object_surface.py
16_export_ladder_representation.py
```

### Artefatos

```text
ladder-capabilities.json
ladder-api-surface.json
ladder-export-sample/
ladder-discovery-report.md
```

### Gate L1

Só avançar quando pelo menos uma destas fontes estiver confirmada:

```text
PLCopen XML
XML interno CODESYS/MasterTool
API de networks/elements/connections
exportação nativa estruturada
```

Se nenhuma fonte existir, registrar Ladder como inventariável, mas semanticamente indisponível.

### Commit sugerido

```text
feat: discover read-only Ladder representation
```

---

## Fase L2 — Aquisição Ladder bruta

### Objetivo

Extrair e preservar a representação Ladder sem tentar interpretá-la.

### Estrutura sugerida

```text
snapshot/
└── graphic-objects/
    └── <node_id>__<nome>/
        ├── metadata.json
        ├── declaration.st
        ├── implementation.xml
        ├── original-export.bin
        └── checksums.sha256
```

O nome real do arquivo dependerá do formato descoberto.

### Regras

* preservar o conteúdo original;
* não reformatar XML;
* calcular checksum;
* registrar versão do MasterTool;
* registrar o método usado na aquisição;
* não modificar o projeto;
* falha em uma POU não deve abortar todo o snapshot.

### Gate L2

Duas exportações consecutivas da mesma POU sem alteração devem produzir o mesmo conteúdo semântico ou uma normalização determinística documentada.

### Commit sugerido

```text
feat: add read-only Ladder artifact export
```

---

## Fase L3 — Modelo intermediário gráfico

### Objetivo

Converter formatos específicos do MasterTool para uma representação independente do fabricante.

### Modelo proposto

```text
GraphicPOU
├── language
├── networks[]
├── variables[]
├── source
└── diagnostics[]

Network
├── id
├── order
├── title
├── comment
├── elements[]
├── connections[]
└── source

Element
├── id
├── kind
├── variable
├── block_type
├── attributes
├── inputs[]
├── outputs[]
└── source

Connection
├── source_element
├── source_pin
├── target_element
├── target_pin
└── branch
```

### Elementos iniciais

```text
power_rail
contact
coil
function
function_block
connector
branch
return
jump
label
```

### Tipos de contato

```text
normally_open
normally_closed
positive_edge
negative_edge
```

### Tipos de bobina

```text
normal
negated
set
reset
```

### Gate L3

Uma rede Ladder sintética deve ser carregada no modelo e serializada novamente sem perder:

* elementos;
* conexões;
* ordem;
* variáveis;
* comentários;
* localização de origem.

### Commit sugerido

```text
feat: add canonical graphic logic model
```

---

## Fase L4 — Parser estrutural Ladder

### Objetivo

Reconstruir a topologia lógica das redes.

### Suporte inicial

* contatos em série;
* contatos em paralelo;
* bobina simples;
* bobina negada;
* set/reset;
* blocos de função;
* entradas e saídas de blocos;
* branches;
* comparadores;
* timers e contadores;
* comentários de rede.

### Exemplo

Rede:

```text
Start ──┬── Permissivo ─────( Equipamento )
        │
Equipamento ──┘
```

Árvore lógica:

```text
WRITE Equipamento
└── AND
    ├── OR
    │   ├── READ Start
    │   └── READ Equipamento
    └── READ Permissivo
```

### Diagnósticos necessários

```text
open_connection
unknown_element
unsupported_branch
multiple_output_paths
cyclic_network
missing_variable
unconnected_pin
```

### Regras

* nenhuma rede inválida pode travar o parser;
* cada rede deve ter resultado independente;
* ciclos devem ser detectados;
* elementos não suportados devem permanecer no modelo;
* nunca inventar ligação ausente.

### Gate L4

Fixtures Ladder sintéticas devem produzir topologias previsíveis e determinísticas.

### Commit sugerido

```text
feat: parse Ladder network topology
```

---

## Fase L5 — Semântica Ladder

### Objetivo

Transformar a topologia em símbolos, referências, leituras, escritas e chamadas.

### Regras iniciais

| Elemento             | Classificação         |
| --------------------- | --------------------- |
| Contato              | leitura               |
| Contato negado       | leitura               |
| Bobina               | escrita               |
| Bobina SET           | escrita               |
| Bobina RESET         | escrita               |
| Variável de retenção | leitura e escrita     |
| Entrada de FB        | leitura               |
| Saída de FB          | escrita               |
| IN_OUT               | leitura e escrita     |
| Callee de bloco      | chamada               |
| Comparador           | leitura dos operandos |

### Exemplo

```text
Equipamento
```

aparecendo como contato e bobina na mesma rede:

```text
read_write
```

### Saídas

```text
ladder-references.json
ladder-calls.json
ladder-read-write.json
ladder-networks.json
ladder-diagnostics.json
```

### Evidências

Cada ocorrência deve preservar:

* POU;
* rede;
* elemento;
* tipo de elemento;
* variável;
* arquivo de origem;
* linha/posição XML ou identificador estrutural;
* regra aplicada;
* estado de resolução;
* confiança.

### Gate L5

Perguntas determinísticas devem funcionar para uma POU exclusivamente Ladder:

```text
find reads Start
find writes Equipamento
find calls Temporizador
find callers FB_Motor
```

### Commit sugerido

```text
feat: add Ladder semantic indexing
```

---

## Fase L6 — Unificação com o índice ST

### Objetivo

Fazer ST e Ladder aparecerem na mesma consulta.

### Modelo

```text
references.json
├── ST
├── Ladder
├── FBD
└── SFC
```

Cada evidência deve indicar:

```json
{
  "language": "ladder",
  "pou": "ControleMotor",
  "network": 3,
  "element": "coil",
  "name": "MotorLigado",
  "access": "write"
}
```

### Consultas esperadas

```text
Onde MotorLigado é escrito?
Quem lê PermissivoGeral?
Quais POUs chamam FB_Motor?
Em quais redes esse alarme é acionado?
```

### Compatibilidade

A API Python, CLI, respostas fundamentadas e MCP não devem precisar conhecer detalhes do parser Ladder. Devem apenas consumir o índice unificado.

### Gate L6

O mesmo símbolo usado em ST e Ladder deve retornar evidências das duas linguagens, ordenadas deterministicamente.

### Commit sugerido

```text
feat: unify ST and Ladder query indexes
```

---

## Fase L7 — Validação real Ladder

### Objetivo

Validar o parser contra projetos reais diferentes.

### Matriz mínima

* POU Ladder simples;
* múltiplas redes;
* branches paralelos;
* selagem;
* set/reset;
* TON;
* TOF;
* CTU;
* chamada de FB;
* comparadores;
* variáveis GVL;
* STRUCT/DUT;
* arrays;
* elementos específicos Altus;
* redes incompletas;
* projeto misto ST/Ladder.

### Método de validação

Para cada rede:

```text
interpretação manual
vs.
modelo produzido
vs.
índices gerados
vs.
resposta da consulta
```

### Métricas

```text
networks_total
networks_supported
networks_partial
networks_failed
elements_total
elements_unknown
references_resolved
references_partial
references_unresolved
```

### Gate L7

A cobertura deve ser explícita. O sistema não precisa suportar 100% dos elementos para ser utilizável, mas não pode omitir silenciosamente o que não compreende.

### Marco sugerido

```text
v0.2.0-ladder-preview
```

---

## Fase L8 — FBD e SFC

Depois do modelo gráfico canônico, FBD e SFC devem reutilizar a mesma infraestrutura.

### FBD

Reutiliza:

* blocos;
* pinos;
* conexões;
* chamadas;
* read/write;
* resolução de tipos.

Adições específicas:

* ordem de execução;
* EN/ENO;
* feedback;
* conexões múltiplas;
* blocos matemáticos e lógicos.

### SFC

Modelo específico:

```text
SFC
├── steps
├── transitions
├── actions
└── connections
```

Análises:

* estados;
* condições de transição;
* ações ativas;
* caminhos possíveis;
* etapas sem saída;
* transições impossíveis;
* ciclos.

### Commits futuros

```text
feat: add FBD semantic indexing
feat: add SFC state-machine indexing
```

---

# 5. Roadmap geral do produto

## v0.2 — Snapshot portátil e Ladder

### Objetivo

Executar em diferentes projetos MasterTool e criar um pacote completo no PC.

### Entregas

* orquestrador de aquisição;
* classificação de linguagens;
* exportação ST;
* exportação Ladder bruta;
* inventário de aplicações;
* tasks;
* bibliotecas;
* hardware;
* relatório de cobertura;
* indexação automática;
* pacote portátil.

### Estrutura

```text
workspace/projects/<project-id>/<run-id>/
├── snapshot/
├── index/
├── reports/
├── diagnostics/
└── checksums.sha256
```

### Comando futuro

```text
mastertool-bridge snapshot
```

### Gate

Um projeto novo deve ser adquirido, indexado e disponibilizado por MCP sem ajustes manuais no código.

---

## v0.3 — Cobertura semântica completa

### Entregas

* Ladder semanticamente indexado;
* ENUM;
* UNION;
* interfaces;
* methods;
* properties;
* actions;
* namespaces;
* FBD inicial;
* SFC inicial;
* tasks e associação de programas;
* catálogo de bibliotecas externas;
* mapeamento de hardware e I/O.

### Gate

A ferramenta deve produzir um relatório de cobertura por linguagem e objeto.

---

## v0.4 — Compreensão de engenharia

### Entregas

* grafo de dependências;
* fluxo de dados;
* máquinas de estado;
* permissivos;
* intertravamentos;
* alarmes;
* timers;
* sequências;
* vínculos entre software e I/O;
* análise de impacto;
* comparação semântica entre versões.

### Consultas futuras

```text
Por que o motor MT01 não liga?
Qual condição bloqueia a descarga da BL5?
O que acontece depois do estado 3?
Quais alarmes dependem deste sensor?
Que partes do sistema serão afetadas por esta mudança?
```

### Regra

A resposta pode ser explicativa, mas cada afirmação deve apontar para evidências determinísticas.

---

## v0.5 — Documentação automática

### Documentos

* descritivo lógico;
* manual de operação;
* manual de manutenção;
* documentação por equipamento;
* matriz de permissivos;
* matriz de intertravamentos;
* matriz de alarmes;
* lista de I/O;
* mapa de comunicação;
* diagramas de estados;
* relatório de alterações.

### Classificação das informações

```text
confirmado_pelo_codigo
inferido_da_logica
fornecido_pelo_usuario
nao_determinado
```

### Rastreabilidade

Cada trecho documental deve guardar:

* snapshot de origem;
* objeto;
* rede ou arquivo;
* linha ou elemento;
* checksum;
* regra que originou a afirmação.

### Atualização incremental

Quando o projeto mudar:

```text
diff semântico
→ evidências alteradas
→ seções potencialmente desatualizadas
→ atualização assistida
```

---

## v0.6 — Agentes especializados

### Agente de suporte técnico

* localizar bloqueios;
* explicar alarmes;
* listar variáveis a monitorar;
* sugerir sequência de diagnóstico;
* gerar checklist de campo.

### Agente de operação

* explicar sequência operacional;
* informar condições de partida;
* orientar recuperação após falha;
* traduzir lógica para linguagem operacional.

### Agente de manutenção

* localizar sensores e atuadores;
* identificar permissivos;
* montar procedimentos de teste;
* relacionar falhas e causas prováveis.

### Agente de engenharia

* analisar impacto;
* revisar código;
* comparar versões;
* localizar duplicações;
* propor refatorações;
* gerar documentação técnica.

### Arquitetura

```text
Agente
→ tools MCP
→ consultas determinísticas
→ grafos
→ evidências
→ resposta
```

O agente não deve receber acesso irrestrito aos arquivos quando uma ferramenta determinística puder responder.

---

## v0.7 — Change sets e escrita controlada

### Objetivo

Permitir que agentes preparem alterações sem modificar diretamente o projeto real.

### Fluxo

```text
pedido
→ plano
→ change set
→ validação
→ revisão humana
→ aplicação em cópia
→ build
→ diagnósticos
→ diff
→ aprovação
```

### Formato de change set

```json
{
  "target_project": "...",
  "base_hash": "...",
  "operations": [
    {
      "operation": "create_function_block",
      "name": "FB_Motor",
      "declaration": "...",
      "implementation": "..."
    }
  ]
}
```

### Primeira prova de escrita

Somente:

```text
criar FB_AI_TESTE
→ salvar uma cópia
→ fechar
→ reabrir
→ confirmar persistência
→ build
```

Não chamar o bloco, alterar hardware ou fazer download.

### Gates obrigatórios

* cópia descartável;
* hash de precondição;
* backup;
* diff;
* build;
* revisão humana;
* nenhuma operação online.

---

## v0.8 — Geração de módulos

### Objetivo

Criar partes completas de um projeto a partir de requisitos.

### EntradasExemplo

* descrição do equipamento;
* lista de I/O;
* estados;
* permissivos;
* alarmes;
* padrão de programação;
* blocos existentes;
* critérios de aceitação.

### Saídas

* DUTs;
* GVLs;
* FBs;
* programas;
* chamadas;
* testes;
* documentação;
* change set aplicável.

### Ciclo

```text
gerar
→ aplicar em cópia
→ compilar
→ interpretar erros
→ corrigir
→ recompilar
→ apresentar para revisão
```

---

## v1.0 — Engenharia assistida por agentes

### Objetivo

Gerar um projeto completo e compilável a partir de uma especificação de engenharia.

### EntradasExemplo

* memorial descritivo;
* arquitetura da planta;
* lista de equipamentos;
* matriz de I/O;
* redes;
* hardware;
* filosofia de controle;
* requisitos de segurança;
* padrões do cliente.

### Saídas

* arquitetura do projeto;
* hardware configurado;
* tipos;
* variáveis;
* POUs;
* tarefas;
* lógica;
* alarmes;
* telas;
* testes;
* documentação;
* relatório de validação.

### Regra permanente

Mesmo em uma versão autônoma:

```text
nenhum download automático
nenhum force
nenhuma operação online sem autorização
nenhuma substituição do gate humano de segurança
```

---

# 6. Ordem recomendada de execução

```text
1. Inventário de POUs gráficas
2. Descoberta da representação Ladder
3. Exportação Ladder bruta
4. Modelo gráfico canônico
5. Parser de redes
6. Semântica read/write/calls
7. Unificação ST + Ladder
8. Validação em projetos reais
9. Snapshot universal
10. FBD e SFC
11. Grafos de engenharia
12. Geração de documentação
13. Agentes especializados
14. Diff semântico
15. Change sets
16. Escrita sintética em cópia
17. Build e correção iterativa
18. Geração de módulos
19. Geração de projetos completos
```

---

# 7. Próxima fatia concreta

O próximo commit deve iniciar pela descoberta, não pelo parser:

```text
feat: inventory and probe Ladder project objects
```

Escopo:

* localizar POUs Ladder;
* registrar identidade e linguagem;
* verificar declaração e implementação disponíveis;
* inspecionar somente membros confirmados;
* procurar fonte estruturada de implementação;
* gerar relatório de capacidade;
* não interpretar redes ainda;
* não modificar o projeto.

Saídas:

```text
ladder-object-inventory.json
ladder-capabilities.json
ladder-api-surface.json
ladder-discovery-report.md
```

Critério para avançar:

```text
Uma representação estrutural real de pelo menos uma POU Ladder foi extraída, preservada e validada.
```

Esse é o gate que determinará o desenho técnico do parser Ladder. Implementar a semântica antes de conhecer o formato real criaria uma arquitetura baseada em suposições.

---

# 8. Estado de execução (registro vivo, atualizado a cada avanço)

## L0 — Inventário e classificação: **CONCLUÍDA** (validada ao vivo em 2026-07-24)

**Reconhecimento offline inicial (2026-07-24)**, contra os dois exports reais já
capturados e validados (`2026-07-23_17-29-54_13_validate_text_exporter` e
`2026-07-24_14-30-44_13_validate_text_exporter`, ambos de
`ExemploPlanta V1.0.project`, idênticos entre si — ver
relatorios de validacao internos (nao publicados)) encontrou 25 candidatos
usando uma regra manual simplificada. Essa regra foi depois formalizada e
implementada em duas ferramentas independentes (mesma regra documentada,
sem código compartilhado — mesmo padrão já usado entre
`read_only_project_scanner.py`/`read_only_text_exporter.py`):

1. **`src/mastertool_bridge/discovery/graphic_language_scan.py`** (Python
   3.11, offline, sobre exports já capturados) — o conjunto de `type_guid`
   "conhecido com implementação textual" agora é **derivado
   dinamicamente** a cada execução (nunca hardcoded), tornando a ferramenta
   reutilizável em qualquer projeto, não só `ExemploPlanta V1.0.project`.
2. **`scripts/mastertool/common/graphic_language_inventory.py`** +
   **`scripts/mastertool/probes/14_inventory_graphic_pous.py`** (IronPython
   2.7, para rodar dentro do MasterTool real) — mesma regra, aplicada ao
   vivo via navegação já aprovada + os 2 indicadores tri-state já
   confirmados (`has_textual_declaration`/`has_textual_implementation`),
   sem ler `.text` nem sondar nenhuma API nova.

**Resultado confirmado com a regra final** (offline, contra os 2 exports
reais, byte-idêntico entre as duas capturas independentes): de 92 objetos,
`{supported: 14, partially_supported: 25, unsupported: 24, unknown: 29}`
— os 25 `partially_supported` incluem `StartPrg`/`UserPrg` (chamados por
`MainPrg`, nunca antes examinados quanto à própria implementação);
`MainPrg`/`SpecialVariablesPrg` confirmados `supported`. **Evidência, não
prova**: `partially_supported` significa "candidato forte a implementação
não textual", nunca "confirmado Ladder/FBD/SFC especificamente".

**Achado colateral honesto**: `flat-objects.json` não tem um campo
`is_folder` confiável sem recorrer a um `type_guid` específico do projeto
(proibido em código de produção) — reportado como `None` (desconhecido)
em vez de adivinhado. A execução ao vivo resolveu essa lacuna (ver abaixo).

### Execução real dentro do MasterTool — 2026-07-24 15:56 (fecha a Fase L0)

O usuário executou `probes/14_inventory_graphic_pous.py` dentro do
MasterTool IEC XE 3.63 real (`ExemploPlanta V1.0.project`, Device NX3005),
saída em `workspace/exports/2026-07-24_15-56-25_14_inventory_graphic_pous/`
(diretório fora do versionamento por `.gitignore`, como todo export).

**Integridade e segurança da execução** (verificadas diretamente sobre os
artefatos, não sobre o relato da tela):

- `checksums.sha256`: **8/8 OK**.
- `errors.json`: `[]`; `report.json` → `failed_nodes=0`, `partial_nodes=0`,
  `field_errors=0`, `collection_errors=0`, `index_errors=0`,
  `duplicate_object_guids=0`, `scan_complete=true`.
- Identidade da Application **confirmada nos 3 campos** (`name`,
  `object_guid=7bd30f35-…`, `type_guid=639b491f-…`),
  `aborted_due_to_identity_mismatch=false`.
- Nenhum limite atingido (`max_depth`/`max_total_nodes`/`max_children_per_node`
  todos `false`; profundidade máxima real = 3).
- `safety_declaration` integralmente fail-closed: `read_only=true`,
  `text_content_read=false`, `textual_declaration_text_accessed=false`,
  `textual_implementation_text_accessed=false`, `project_write=false`,
  `project_save=false`, `project_close=false`, `compilation=false`,
  `download=false`, `online_access=false`, `force=false`,
  `object_creation=false`, `object_modification=false`,
  `new_member_probing=false`, `find_used=false`,
  `device_repository_access=false`, `device_configuration_access=false`.

**Critério de aprovação da fase — convergência das duas implementações
independentes** (Python 3.11 offline × IronPython 2.7 ao vivo, sem código
compartilhado):

- 92 objetos ao vivo × 92 offline; **conjuntos de `node_id` idênticos**
  (nenhum só de um lado).
- **0 divergências** campo a campo em `state`, `name`, `type_guid`,
  declaração textual e implementação textual, nos 92 objetos.
- Contagens idênticas: `{supported: 14, partially_supported: 25,
  unsupported: 24, unknown: 29}`.
- 0 drift entre as duas capturas offline independentes (2026-07-23 e
  2026-07-24), confirmando que o resultado não depende da sessão.

**Fato novo que só a execução ao vivo pôde estabelecer** — o campo
`is_folder`, que offline era `None` por honestidade:

- **Nenhum dos 25 `partially_supported` é pasta** (`is_folder=false` em
  todos os 25). Os candidatos a Ladder/FBD/SFC são objetos reais, não
  containers de organização — o risco de a lista estar inflada por pastas
  está descartado.
- Dos 24 `unsupported`, 13 são pastas, 10 não são e 1 é o nó raiz
  `application` (`is_folder=null`, sem `type_guid`) — comportamento
  correto, não lacuna.
- Os 29 `unknown` são todos `is_folder=false` com `child_count=0` e
  correspondem a DUTs/GVLs (`Equipamento`, `DrivesExemplo`, `VarGlobaisExemplo`,
  `VarEquipamentosExemplo`, `System_Diagnostics`, …): objetos que por natureza não
  têm corpo de implementação. Classificá-los como `unknown` é o
  comportamento correto da regra (não há referência de comparação com
  implementação textual para esses `type_guid`), não uma falha de
  cobertura.

**Veredito da Fase L0: APROVADO — gate de L1 aberto.**

**Registro de numeração** (evitar colisão futura): o slot `15_` já está
ocupado por `probes/15_validate_command_line_execution.py` (trilha de
automação, `docs/15-automation-launcher-roadmap.md`). O probe de superfície
de objeto Ladder previsto na Fase L1 como `15_probe_ladder_object_surface.py`
deve ser criado como **`16_probe_ladder_object_surface.py`**, e o de
exportação como **`17_export_ladder_representation.py`**.

## L1 — Sondagem de superfície: **EXECUTADA em 2026-07-27, NÃO FECHADA**

Primeira execução real dentro do MasterTool 3.63 em 2026-07-27 11:48
(run `2026-07-27_11-47-02`), via
`run_supervised_snapshot.ps1 -ProbeLadderSurface -Execute`. Artefatos em
`workspace/exports/2026-07-27_11-48-02_16_probe_ladder_object_surface/`.

**Higiene da execução, verificada nos artefatos (não na tela):**

- checksums **12/12 OK**;
- `aborted=false`, `target_identity_confirmed=true` — os 4 campos de
  identidade de `application/9/4` conferidos, `mismatches: []`;
- `safety-declaration.json` inteira `false`: sem `project_modified`,
  `save_called`, `build_called`, `online_operation`, `export_called`,
  `import_called`, `text_document_read`/`write`;
- `safe_getter_invocations=0` — nenhum getter chegou a ser chamado, porque
  todos os 9 candidatos são métodos (ver abaixo).

### Achado positivo: a rota para Ladder existe e tem nome

Os 9 candidatos a representação são **todos métodos de export/import**:
`export_xml` (4 sobrecargas), `import_xml` (4 sobrecargas), `export_native`
(1). Nenhum foi invocado (`invoked=false`, `reason_not_invoked="member is a
method, not a property/getter"`) — coerente com o contrato read-only da
fase.

O fato decisivo veio de uma **assinatura**, não de uma chamada: uma
sobrecarga de `import_xml` recebe um parâmetro do tipo
`_3S.CoDeSys.PLCopenXML.ConflictResolve`. Isso identifica o formato do
`export_xml` como **PLCopen XML** — o padrão de intercâmbio IEC 61131-3,
que representa LD/FBD/SFC graficamente. É a rota mais promissora para L2, e
não é suposição: o tipo .NET veio da reflexão real sobre o objeto.

Vale registrar também o parâmetro `bPlainText: System.Boolean` na
sobrecarga de 5 argumentos de `export_xml`.

### Por que a fase NÃO está fechada: falso-negativo comprovado no método

O relatório sugere que nenhuma property dá acesso direto à representação.
**Essa conclusão negativa não se sustenta**, e o próprio dado prova isso.

O probe enumera via `GetType().GetProperties()/GetMethods()` — reflexão
.NET pura sobre o tipo CLR. Ele encontrou 13 properties e 16 métodos
distintos. Mas `textual_declaration` **não está entre eles**, apesar de ser
um membro comprovadamente funcional: é exatamente o que o
`ReadOnlyTextExporter` usa para ler os 68 objetos de texto, e está
registrado em `docs/api/mastertool-api-observations.md`.

`textual_declaration` funciona portanto como **caso-controle**: um membro
que sabidamente existe e funciona, e que o método de enumeração não vê. A
causa está visível na própria lista de interfaces do artefato — o objeto é
um `ExtendedObject[IScriptObject]` e implementa `IExtendedObject`; o
ScriptEngine anexa extensões dinamicamente (`Extender`), e a reflexão sobre
o tipo CLR não as alcança.

Consequência: a ausência de um acessor Ladder nesta lista **não é evidência
de que ele não exista**. Concluir o contrário desenharia L2 sobre uma
ausência que o método não é capaz de detectar — precisamente o que a regra
permanente desta trilha proíbe.

**Veredito da Fase L1: parcial. Gate de L2 permanece FECHADO.**

Falta, antes de fechar: uma segunda passada de enumeração sobre a
superfície **dinâmica** (`dir()` do lado IronPython + `hasattr` contra a
whitelist), além da reflexão .NET, para separar "não existe" de "existe e
não é visível por reflexão". Só então a escolha entre a rota PLCopen XML e
uma eventual rota por extensão poderá ser feita sobre evidência.

Ressalva de escopo para o passo seguinte: `export_xml` **escreve arquivo em
disco**, o que sai do perfil estritamente read-only vigente. Exige
autorização humana explícita e destino descartável definido pelo operador.

## L2–L8, v0.2–v1.0: bloqueadas

L2 em diante continua aguardando o fechamento de L1 antes de qualquer
decisão de arquitetura — nenhum modelo canônico, parser ou formato de
artefato será desenhado por suposição.

---

# 9. Automação — comando único (trilha paralela, registrada 2026-07-24)

Ver `docs/15-automation-launcher-roadmap.md` para a especificação
completa. Resumo: substituir a execução manual de cada script por um
único comando (`mastertool-bridge snapshot --project ... --output ...`),
gated em 4 etapas (A: prova mínima de linha de comando no `MT8500.exe`
real → B: runner automático → C: launcher externo → D: pipeline completo).
Etapa A é a única que pode ser construída sem confirmação prévia (é a
própria prova); B/C/D ficam bloqueadas até a Etapa A ser executada e
observada pelo usuário. Esta trilha é independente da trilha Ladder
(L0–L8) — ambas podem avançar em paralelo, mas nenhuma das duas antecipa
resultado da outra.

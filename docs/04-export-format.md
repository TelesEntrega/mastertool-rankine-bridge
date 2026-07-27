# Formato do export

Cada export é um diretório **imutável**:

```text
workspace/exports/
└── 2026-07-23_09-45-10_nome-projeto/
    ├── export-manifest.json      # obrigatório (schema project-manifest)
    ├── project.json
    ├── environment.json
    ├── project-tree.json
    ├── libraries.json
    ├── tasks.json
    ├── devices.json
    ├── compilation.json
    ├── errors.json
    ├── checksums.sha256          # "hash  caminho/relativo" por linha
    ├── objects/
    │   ├── programs/ | function-blocks/ | functions/ | methods/
    │   ├── actions/ | properties/ | gvls/ | duts/
    │   ├── visualizations/ | other/
    ├── plcopen/                  # exports PLCopen XML quando disponíveis
    ├── raw/                      # exports nativos brutos
    ├── reports/                  # saídas da CLI externa (índice, análises)
    └── logs/
```

## Objeto textual

```text
objects/function-blocks/ControleMotor/
├── metadata.json        # schema object.schema.json
├── declaration.st
├── implementation.st
├── raw-export.xml       # quando houver export nativo
└── export-errors.json   # erros individuais (export nunca para por 1 objeto)
```

`metadata.json` — campos e exemplo no schema
`src/mastertool_bridge/schemas/object.schema.json`. Regras:

- `export_status`: `success` | `partial` | `failed`;
- hashes SHA-256 de declaração/implementação quando exportadas;
- campos indisponíveis na API real ficam `null` (nunca inventados).

## Objetos gráficos (LD/FBD/SFC/visualizações)

Ordem de tentativa: 1) PLCopen XML → `plcopen/`; 2) export nativo → `raw/`;
3) somente `metadata.json` com aviso. O fracasso de um objeto é registrado em
`export-errors.json` e o export continua.

## Manifesto

`export-manifest.json` segue `schemas/project-manifest.schema.json`:
identificação do projeto, ambiente, estatísticas, configuração usada e o bloco
`safety` que declara `mode: read_only` e `project_modified: false`. A CLI
`mastertool-bridge validate-export` rejeita manifestos fora do schema.

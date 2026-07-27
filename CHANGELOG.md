# Changelog

Formato baseado em [Keep a Changelog](https://keepachangelog.com/pt-BR/1.1.0/).

## [0.1.0] - 2026-07-23

### Adicionado
- Estrutura inicial do repositório (primeira entrega — Fase 0, somente leitura).
- Scripts IronPython de descoberta: `00_smoke_test`, `01_discover_environment`,
  `02_dump_api_surface`, `03_list_project_tree`.
- Módulos comuns IronPython (`scripts/mastertool/common/`).
- CLI externa `mastertool-bridge` com `validate-export`, `inspect`, `index`,
  `find-symbol`, `find-reads`, `find-writes`, `compare`, `analyze`,
  `build-agent-context`, `validate-change-set`.
- Schemas JSON iniciais (manifesto, objeto, compilação, referências, change set).
- Política de segurança (`config/safety-policy.yaml`) e documentação (`docs/`).
- Testes unitários da camada externa.

### Segurança
- Modo somente leitura obrigatório; importação (`09`–`11`) desabilitada por projeto.

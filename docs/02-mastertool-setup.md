# Preparação do MasterTool IEC XE 3.63

## Pré-requisitos

- MasterTool IEC XE 3.63 instalado (base CODESYS com ScriptEngine/IronPython).
- Um projeto de teste aberto (nunca o projeto oficial de produção nas primeiras execuções).
- Este repositório clonado em um caminho SEM acentos, se possível (evita
  problemas de encoding no IronPython).

## Executando um script

1. Abra o MasterTool com o projeto carregado.
2. Localize o comando de execução de scripts. Candidatos típicos:
   - *Ferramentas → Scripting → Executar arquivo de script...*
   - *Tools → Scripting → Execute Script File...*
3. Selecione o script desejado em `scripts/mastertool/`.
4. A saída aparece no painel de mensagens do MasterTool e nos logs em
   `workspace/logs/`.

> **Registre o caminho de menu real** encontrado na sua instalação em
> [03-scripting-discovery.md](03-scripting-discovery.md) — ele varia por versão/idioma.

## Ordem de execução (Fase 0)

1. `00_smoke_test.py` — sem risco; apenas imprime e grava log.
2. `01_discover_environment.py` — gera `environment.json/.md`.
3. `02_dump_api_surface.py` — gera `api-surface.json/.md`.
4. `03_list_project_tree.py` — gera `project-tree.json/.csv/.md`.

Nenhum deles modifica o projeto. Depois de rodar, devolva os arquivos gerados
em `workspace/exports/` para análise e atualização de
`docs/api/mastertool-api-observations.md`.

## Solução de problemas

Ver [09-troubleshooting.md](09-troubleshooting.md).

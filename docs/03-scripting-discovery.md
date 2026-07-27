# Descoberta do scripting no MasterTool 3.63 — registro de campo

> **Este documento registra apenas fatos observados no ambiente real.**
> Estado atual: **`00_smoke_test.py` executado com sucesso** em 2026-07-23
> contra um projeto real (`ExemploPlanta V1.0.project`). Scripts 01-03 ainda não
> rodados — aguardando decisão de ampliar o escopo de introspecção (ver
> "Achado importante" em [api/mastertool-api-observations.md](api/mastertool-api-observations.md)).

## Ambiente

- Versão do MasterTool: MasterTool IEC XE 3.63 (confirmado pelo título da janela)
- Versão do ScriptEngine: `ScriptEngine.plugin 4.1.0.0` (via `sys.version`, ver nota abaixo)
- Versão do interpretador Python: **não obtida ainda** — `sys.version` neste
  host retorna `"MT8500.exe MasterTool IEC XE, ScriptEngine.plugin 4.1.0.0"`
  em vez de um número de versão. `sys.platform == "cli"` confirma IronPython.
  Assumido IronPython 2.7 (stdlib embarcada em `ScriptLib/4.1.0.0/` confirma
  arquivos como `argparse.py`/`clrtype.py`, típicos de Python 2.7), mas o
  número exato (`2.7.x`) segue sem confirmação direta.
- Caminho de menu para executar scripts: menu **Ferramentas** (visível na
  janela); submenu exato ainda não registrado — confirmar na próxima rodada.
- Existe console interativo de scripting? _pendente_ (não testado)

## Objetos globais observados

| Nome | Presente? | Tipo observado | Observações |
|------|-----------|----------------|-------------|
| `projects` | **Sim** (confirmado 2026-07-23) | `ScriptProjects` | `.primary` presente e truthy |
| `system` | **Sim** (confirmado 2026-07-23) | `SystemImpl` | membros ainda não sondados |
| `librarymanager` | _pendente_ | | não sondado por `00_smoke_test.py` (fora da whitelist) |
| `device_repository` | _pendente_ | | não sondado por `00_smoke_test.py` (fora da whitelist) |
| `online` | _pendente_ | | **nunca sondado nem invocado** — excluído deliberadamente da whitelist de `00_smoke_test.py` |

`projects.primary`: presente, tipo `ExtendedObject[IScriptProject]`,
`.path` legível (retornou o caminho real do `.project` aberto). `dir()` sobre
esse objeto voltou **vazio** — ver achado importante em
[api/mastertool-api-observations.md](api/mastertool-api-observations.md),
relevante antes de rodar `02_dump_api_surface.py`.

## APIs disponíveis / ausentes

_Preencher com base em `api-surface.json` (script 02, ainda não executado).
Detalhes por objeto em
[api/mastertool-api-observations.md](api/mastertool-api-observations.md)._

## Limitações encontradas

- `sys.version` não serve como fonte da versão do Python/IronPython neste
  host (ver seção "Ambiente" acima).
- `dir()` sobre o objeto `ExtendedObject[IScriptProject]` (`projects.primary`)
  retornou vazio mesmo com propriedades acessíveis via `getattr` direto
  (`.path` funcionou). Suspeita: o wrapper usa o protocolo dinâmico do DLR
  (`IDynamicMetaObjectProvider`) em vez de reflection tradicional. Precisa de
  investigação antes de confiar em `dir()`-based introspection
  (`02_dump_api_surface.py`, `tree_walker.py`) para este tipo de objeto.

## Testes realizados

| Data | Script | Projeto usado | Resultado | Artefatos |
|------|--------|---------------|-----------|-----------|
| 2026-07-23 | `00_smoke_test.py` | `ExemploPlanta V1.0.project` (real, device NX3005) | OK — 0 erro(s)/0 advertência(s) na aba de mensagens do script | `workspace/logs/2026-07-23_10-28-07_00_smoke_test/report.json` + `.md` |

## Roteiro de teste manual (por script)

### 00_smoke_test.py — **VALIDADO em 2026-07-23**
- **Pré-condições**: MasterTool aberto com projeto de teste carregado.
- **Passos**: executar o script pelo menu de scripting (Ferramentas).
- **Resultado esperado**: mensagens `[OK] Script executado.`, dados do
  interpretador, presença de `projects`/`system`, caminho do projeto;
  diretório com timestamp criado em `workspace/logs/`.
- **Resultado obtido**: conforme esperado. `projects`/`system` presentes
  (tipos `ScriptProjects`/`SystemImpl`), `projects.primary` presente,
  caminho do projeto lido corretamente, 0 erros. Ver relatório completo em
  `workspace/logs/2026-07-23_10-28-07_00_smoke_test/`.
- **Risco**: nenhum (somente leitura) — confirmado, nenhuma escrita/compilação/
  acesso online foi solicitado.
- **Rollback**: não se aplica.

### 01_discover_environment.py
- **Resultado esperado**: `workspace/exports/<ts>_discovery/environment.json|.md`.
- **Risco**: nenhum; o script não invoca métodos, apenas dir()/getattr guardado.

### 02_dump_api_surface.py
- **Resultado esperado**: `api-surface.json|.md` com propriedades/métodos por objeto.
- **Risco**: nenhum; introspecção usa a classe, não a instância.

### 03_list_project_tree.py
- **Resultado esperado**: `project-tree.json|.csv|.md` com todos os objetos.
- **Risco**: nenhum. Se a API de árvore não existir, o script relata e aborta
  sem tocar no projeto.

## Exemplos mínimos funcionais

_Adicionar aqui os menores trechos de código que comprovadamente funcionaram
no MasterTool 3.63, com data e contexto._
